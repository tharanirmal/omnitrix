"""Embeddings and hybrid search: Postgres full text and pgvector cosine similarity, fused by reciprocal rank
(LR §3.6, §4). Filters (time, people, direction) are applied inside both searches, not after them."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psycopg

Embed = Callable[[list[str]], list[list[float]]]
Ranked = dict[str, list[tuple[int, int]]]       # search name -> [(chunk_id, item_id)] best first
# Fusion settings measured on 500 EnronQA questions (LR §4.4): BM25 is the stronger list here, so meaning search
# counts half, and a small constant rewards top ranks. Standard RRF (k=60, equal weights) scored MRR 0.55 vs 0.61.
RRF_K = 5
WEIGHTS = {"keywords": 1.0, "meaning": 0.5}
POOL = 50           # candidates taken from each search before fusion


@dataclass
class Hit:
    item_id: int
    score: float
    sent_at: datetime | None
    from_addr: str
    subject: str
    text: str
    why: list[str] = field(default_factory=list)


def vector_literal(v: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.5f}" for x in v) + "]"


def embed_pending(conn: psycopg.Connection, embed: Embed, batch: int = 32,
                  on_batch: Callable[[int], None] | None = None, model: str | None = None) -> int:
    """Embed every chunk that has no vector yet or, given `model`, one another embedder made (so a new embedder
    re-embeds only what it has not made). Commits per batch: interruptible and resumable."""
    done = 0
    while rows := conn.execute("SELECT id, header, text FROM chunks WHERE embedding IS NULL OR (%s::text IS NOT NULL "
                               "AND embedding_model IS DISTINCT FROM %s) ORDER BY id LIMIT %s",
                               (model, model, batch)).fetchall():
        vectors = embed([f"{r['header']}\n{r['text']}" for r in rows])
        with conn.cursor() as cur:
            cur.executemany("UPDATE chunks SET embedding = %s::halfvec, embedding_model = %s WHERE id = %s",
                            [(vector_literal(v), model, r["id"]) for r, v in zip(rows, vectors, strict=True)])
        conn.commit()
        done += len(rows)
        if on_batch:
            on_batch(done)
    return done


def ensure_ann_index(conn: psycopg.Connection) -> None:
    """HNSW over chunk vectors, built once after the bulk embedding pass (pgvector defaults: m=16,
    ef_construction=64)."""
    conn.execute("CREATE INDEX IF NOT EXISTS chunks_embedding ON chunks USING hnsw (embedding halfvec_cosine_ops)")
    conn.commit()


def ranked(conn: psycopg.Connection, query: str, qvec: Sequence[float] | None = None, *,
           since: datetime | None = None, until: datetime | None = None, people: Sequence[str] = (),
           direction: str | None = None, pool: int = POOL) -> Ranked:
    """Candidate chunks from each search, best first: 'keywords' always, 'meaning' when a query vector is given.
    `people` are address fragments ('shirley', '@aol.com') matched against sender and recipients."""
    where, params = _filters(since, until, people, direction)
    params |= {"text": query, "n": pool}
    out: Ranked = {}
    if qvec is not None:
        params["q"] = vector_literal(qvec)
        with conn.transaction():
            conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")   # keep scanning until filters are met
            out["meaning"] = [(r["id"], r["item_id"]) for r in conn.execute(
                "SELECT c.id, c.item_id FROM chunks c JOIN items i ON i.id = c.item_id "
                f"WHERE c.embedding IS NOT NULL {where} ORDER BY c.embedding <=> %(q)s::halfvec LIMIT %(n)s", params)]
    # BM25 (k1=1.2, b=0.75) over the postings of the query's most informative words; words in more than 20% of
    # chunks are too common to find or rank anything. Unfiltered, the ranking is cut before any join. Never
    # prepared: a generic plan cannot see which words (and how common), and scans every posting (~40x slower).
    filtered = f"JOIN items i ON i.id = c.item_id WHERE true {where}" if where else ""
    out["keywords"] = [(r["id"], r["item_id"]) for r in conn.execute(
        # a word too new for the lagging statistics gets its document frequency counted from the postings
        "WITH q AS (SELECT l AS lexeme, ln(1 + (s.n - d.df + 0.5) / (d.df + 0.5)) AS idf "
        "           FROM unnest(tsvector_to_array(to_tsvector('english', %(text)s))) l, chunk_stats s, "
        "           LATERAL (SELECT coalesce((SELECT f.df FROM lexeme_idf f WHERE f.lexeme = l), "
        "                                    (SELECT count(*) FROM postings p WHERE p.lexeme = l)) AS df) d "
        "           WHERE d.df > 0 AND d.df <= greatest(0.2 * s.n, 1) ORDER BY idf DESC LIMIT 8), "
        "scored AS (SELECT p.chunk_id, sum(q.idf * p.tf * 2.2 / (p.tf + 1.2 * (0.25 + 0.75 * p.len / s.avgdl))) "
        "                  AS score FROM q JOIN postings p ON p.lexeme = q.lexeme, chunk_stats s GROUP BY p.chunk_id "
        f"          {'' if where else 'ORDER BY score DESC, p.chunk_id LIMIT %(n)s'}) "
        f"SELECT c.id, c.item_id FROM scored JOIN chunks c ON c.id = scored.chunk_id {filtered} "
        "ORDER BY scored.score DESC, c.id LIMIT %(n)s", params, prepare=False)]
    return out


def refresh_stats(conn: psycopg.Connection) -> None:
    """Recompute BM25's corpus statistics (document frequencies, average length). Postings are kept current on
    ingest; the statistics can lag a little behind new items without changing rankings noticeably."""
    for view in ("chunk_stats", "lexeme_idf"):
        conn.execute(f"REFRESH MATERIALIZED VIEW {view}")
    conn.commit()


def fuse(lists: Ranked, rrf_k: int = RRF_K,
         weights: dict[str, float] | None = None) -> list[tuple[int, int, float, list[str]]]:
    """Weighted reciprocal rank fusion, then the best chunk per item: [(chunk_id, item_id, score, why)] best
    first. An item found by different chunks in each list is ranked by its single best chunk."""
    weights = WEIGHTS if weights is None else weights
    fused: dict[int, dict[str, Any]] = {}
    for name, rows in lists.items():
        for rank, (chunk_id, item_id) in enumerate(rows, 1):
            e = fused.setdefault(chunk_id, {"item_id": item_id, "score": 0.0, "why": []})
            e["score"] += weights.get(name, 1.0) / (rrf_k + rank)
            e["why"].append(f"{name} #{rank}")
    best: dict[int, tuple[int, dict[str, Any]]] = {}
    for chunk_id, e in fused.items():
        if e["item_id"] not in best or e["score"] > best[e["item_id"]][1]["score"]:
            best[e["item_id"]] = (chunk_id, e)
    return [(cid, e["item_id"], e["score"], e["why"]) for cid, e in sorted(best.values(), key=lambda t: -t[1]["score"])]


def search(conn: psycopg.Connection, embed: Embed | None, query: str, k: int = 10, *,
           since: datetime | None = None, until: datetime | None = None, people: Sequence[str] = (),
           direction: str | None = None) -> list[Hit]:
    """Best `k` items for `query`: keyword and meaning search over chunks, fused by rank, one hit per item."""
    qvec = embed([query])[0] if embed is not None else None
    top = fuse(ranked(conn, query, qvec, since=since, until=until, people=people, direction=direction))[:k]
    if not top:
        return []
    rows = {r["id"]: r for r in conn.execute(
        "SELECT c.id, c.text, i.sent_at, i.from_addr, i.subject FROM chunks c JOIN items i ON i.id = c.item_id "
        "WHERE c.id = ANY(%s)", ([cid for cid, *_ in top],))}
    return [Hit(item_id, round(score, 5), rows[cid]["sent_at"], rows[cid]["from_addr"], rows[cid]["subject"],
                rows[cid]["text"], why) for cid, item_id, score, why in top]


def _filters(since: datetime | None, until: datetime | None, people: Sequence[str],
             direction: str | None) -> tuple[str, dict[str, Any]]:
    clauses, params = [], {}
    if since:
        clauses.append("i.sent_at >= %(since)s")
        params["since"] = since
    if until:
        clauses.append("i.sent_at < %(until)s")
        params["until"] = until
    if people:
        clauses.append("EXISTS (SELECT 1 FROM unnest(ARRAY[i.from_addr] || i.to_addrs || i.cc_addrs) a "
                       "WHERE a LIKE ANY(%(people)s))")
        params["people"] = [f"%{_like_literal(p.lower())}%" for p in people]
    if direction:
        clauses.append("i.direction = %(direction)s")
        params["direction"] = direction
    return "".join(f" AND {c}" for c in clauses), params


def _like_literal(s: str) -> str:
    """`s` matched literally inside a LIKE pattern ('_' and '%' are wildcards otherwise)."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
