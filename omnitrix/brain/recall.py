"""Scoped recall: the only way agents read the brain.

    question -> 1. find the people / organizations / projects it is about        (plain code)
             -> 2. scope: documents linked to them and their direct neighbours    (graph, SQL)
             -> 3. meaning search + keyword search inside the scope, fused        (pgvector + full text)
             -> 4. a few structured facts: relations, decisions, track records,
                   upcoming meetings                                               (SQL)
             -> 5. trimmed to a token budget, logged in recall_log

Two baselines exist for the benchmark: `vector_all` (classic RAG over every chunk) and `keyword_all`.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from omnitrix.core.clock import Clock
from omnitrix.core.db import Database
from omnitrix.core.ids import new_id

from .ingest import Embedder, load_matcher
from .text import EntityMatcher, estimate_tokens, keyword_tsquery, vector_literal

Strategy = Literal["brain", "vector_all", "keyword_all"]
RRF_K = 60
CANDIDATES = 20
MAX_CHUNKS_PER_DOC = 2
MAX_PER_THREAD = 2         # one email conversation must not fill the whole context
SCOPE_TOO_WIDE = 0.6       # a scope covering more than 60% of documents is no scope at all
NEIGHBOUR_TYPES = ("project", "organization")


class Item(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    doc_type: str
    occurred_at: str | None
    text: str
    score: float
    why: list[str]
    ref: dict = Field(default_factory=dict)       # demo_id / path / filename, for citing and benchmarking


class Fact(BaseModel):
    text: str
    ref: str


class ContextPack(BaseModel):
    query: str
    strategy: str
    entities: list[dict] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)

    def to_prompt(self) -> str:
        """Compact context for an agent's prompt, with numbered sources to cite."""
        lines = []
        if self.facts:
            lines.append("Known facts:")
            lines += [f"- {f.text}" for f in self.facts]
        if self.items:
            lines.append("Sources:")
            for i, it in enumerate(self.items, 1):
                lines.append(f"[{i}] {it.doc_type} '{it.title}' ({(it.occurred_at or '')[:10]}):\n{it.text}")
        return "\n".join(lines)


@dataclass
class _Corpus:
    documents: int
    chunks: int
    tokens: int


class Brain:
    def __init__(self, db: Database, embed: Embedder, clock: Clock):
        self.db = db
        self.embed = embed
        self.clock = clock
        self._matcher: EntityMatcher | None = None
        self._corpus: _Corpus | None = None

    async def refresh(self) -> None:
        """Reload the entity matcher and corpus size (after ingestion)."""
        self._matcher = await load_matcher(self.db)
        row = await self.db.fetchrow("SELECT (SELECT count(*) FROM documents) AS d, count(*) AS c, "
                                     "coalesce(sum(length(text)), 0) AS chars FROM chunks")
        self._corpus = _Corpus(row["d"], row["c"], math.ceil(row["chars"] / 4))

    async def recall(self, query: str, *, agent: str = "cli", strategy: Strategy = "brain", k: int = 5,
                     token_budget: int = 1200, log: bool = True) -> ContextPack:
        if self._matcher is None or self._corpus is None:
            await self.refresh()
        timings: dict[str, float] = {}
        t_all = time.monotonic()

        t = time.monotonic()
        entity_ids = [e for e in self._matcher.find(query) if not self._matcher.is_self(e)]
        timings["entities_ms"] = _ms(t)

        scope_docs: list[str] | None = None
        scope_entities: list[str] = []
        if strategy == "brain" and entity_ids:
            t = time.monotonic()
            scope_entities, scope_docs = await self._scope(entity_ids)
            if len(scope_docs) > SCOPE_TOO_WIDE * self._corpus.documents:
                scope_docs = None
            timings["scope_ms"] = _ms(t)

        qvec = None
        if strategy in ("brain", "vector_all"):
            t = time.monotonic()
            qvec = vector_literal((await self.embed([query]))[0])
            timings["embed_ms"] = _ms(t)

        ranked: dict[str, dict] = {}
        lists: list[list[dict]] = []
        if qvec:
            t = time.monotonic()
            lists.append(await self._vector(qvec, scope_docs))
            timings["vector_ms"] = _ms(t)
        if strategy in ("brain", "keyword_all"):
            t = time.monotonic()
            lists.append(await self._keyword(query, scope_docs))
            timings["keyword_ms"] = _ms(t)

        for lst in lists:
            for rank, row in enumerate(lst):
                entry = ranked.setdefault(row["id"], {**row, "score": 0.0, "why": []})
                entry["score"] += 1 / (RRF_K + rank + 1)
                entry["why"].append(f"{row['via']} #{rank + 1}")
        if strategy == "brain":
            for entry in ranked.values():
                overlap = set(entry["entity_ids"]) & set(entity_ids)
                if overlap:
                    entry["score"] += 0.004 * len(overlap)
                    entry["why"].append("names " + ", ".join(self._matcher.entities[e].name for e in sorted(overlap)))

        fallback = False
        # only when the scope has nothing at all - never pad the context with unrelated documents
        if strategy == "brain" and scope_docs is not None and not ranked:
            fallback = True
            for rank, row in enumerate(await self._vector(qvec, None)):
                if row["id"] not in ranked:
                    ranked[row["id"]] = {**row, "score": 0.5 / (RRF_K + rank + 1), "why": ["outside scope (fallback)"]}

        items = self._select(sorted(ranked.values(), key=lambda r: -r["score"]), k, token_budget)

        facts: list[Fact] = []
        if strategy == "brain":
            t = time.monotonic()
            facts = await self._facts(query, entity_ids)
            timings["facts_ms"] = _ms(t)

        timings["total_ms"] = _ms(t_all)
        scope_chunks = (await self.db.fetchrow("SELECT count(*) AS n FROM chunks WHERE document_id = ANY(%s)",
                                               (scope_docs,)))["n"] if scope_docs is not None else self._corpus.chunks
        returned_tokens = sum(estimate_tokens(i.text) for i in items) + sum(estimate_tokens(f.text) for f in facts)
        stats = {
            "corpus_documents": self._corpus.documents, "corpus_chunks": self._corpus.chunks,
            "corpus_tokens": self._corpus.tokens,
            "scoped": scope_docs is not None, "scope_documents": len(scope_docs) if scope_docs is not None
            else self._corpus.documents, "scope_chunks": scope_chunks,
            "candidates": sum(len(x) for x in lists), "returned_chunks": len(items), "facts": len(facts),
            "returned_tokens": returned_tokens,
            "share_searched": round(scope_chunks / max(1, self._corpus.chunks), 4),
            "share_returned": round(returned_tokens / max(1, self._corpus.tokens), 4),
            "fallback": fallback, **{k2: round(v, 1) for k2, v in timings.items()},
        }
        pack = ContextPack(
            query=query, strategy=strategy, items=items, facts=facts, stats=stats,
            entities=[{"id": e, "name": self._matcher.entities[e].name, "type": self._matcher.entities[e].type}
                      for e in entity_ids])
        if log:
            await self._log(pack, agent, scope_entities, scope_docs or [])
        return pack

    # ------------------------------------------------------------------------------------------ steps

    async def _scope(self, entity_ids: list[str]) -> tuple[list[str], list[str]]:
        """The entities asked about plus their direct project / organization neighbours, and every document
        that mentions any of them."""
        rows = await self.db.fetch(
            "SELECT CASE WHEN r.from_entity = ANY(%s) THEN r.to_entity ELSE r.from_entity END AS other, e.type, e.details "
            "FROM relations r JOIN entities e ON e.id = CASE WHEN r.from_entity = ANY(%s) THEN r.to_entity "
            "ELSE r.from_entity END WHERE (r.from_entity = ANY(%s) OR r.to_entity = ANY(%s)) AND r.valid_to IS NULL",
            (entity_ids, entity_ids, entity_ids, entity_ids))
        scope = list(dict.fromkeys(entity_ids + [r["other"] for r in rows if r["type"] in NEIGHBOUR_TYPES
                                                 and not (r["details"] or {}).get("self")]))
        docs = await self.db.fetch("SELECT DISTINCT document_id FROM mentions WHERE entity_id = ANY(%s)", (scope,))
        return scope, [d["document_id"] for d in docs]

    _SELECT = ("SELECT c.id, c.document_id, c.text, c.entity_ids, d.title, d.doc_type, d.occurred_at, d.meta, "
               "coalesce(em.thread_id, d.id) AS thread FROM chunks c JOIN documents d ON d.id = c.document_id "
               "LEFT JOIN emails em ON em.id = d.meta->>'email_id' ")

    async def _vector(self, qvec: str, scope_docs: list[str] | None) -> list[dict]:
        where = "WHERE c.document_id = ANY(%(scope)s) " if scope_docs is not None else ""
        sql = (f"WITH hits AS MATERIALIZED ({self._SELECT.replace('SELECT ', 'SELECT c.embedding <=> %(q)s::vector AS dist, ', 1)}"
               f"{where}ORDER BY dist LIMIT %(n)s) SELECT * FROM hits ORDER BY dist")
        params = {"q": qvec, "scope": scope_docs, "n": CANDIDATES}
        async with self.db.connection() as conn, conn.transaction():
            if scope_docs is not None:
                # HNSW finds the nearest neighbours first and filters afterwards; with a narrow scope most of
                # them fall outside it. Iterative scans keep searching until enough rows pass the filter
                # (pgvector >= 0.8); the outer ORDER BY restores exact order.
                await conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
            rows = await (await conn.execute(sql, params)).fetchall()
        return [{**r, "via": "meaning"} for r in rows]

    async def _keyword(self, query: str, scope_docs: list[str] | None) -> list[dict]:
        tsq = keyword_tsquery(query)
        if not tsq:
            return []
        scope = "AND c.document_id = ANY(%(scope)s) " if scope_docs is not None else ""
        rows = await self.db.fetch(
            self._SELECT + "WHERE c.tsv @@ to_tsquery('english', %(tsq)s) " + scope +
            "ORDER BY ts_rank_cd(c.tsv, to_tsquery('english', %(tsq)s)) DESC LIMIT %(n)s",
            {"tsq": tsq, "scope": scope_docs, "n": CANDIDATES})
        return [{**r, "via": "keyword"} for r in rows]

    @staticmethod
    def _select(rows: list[dict], k: int, token_budget: int) -> list[Item]:
        items: list[Item] = []
        per_doc: dict[str, int] = defaultdict(int)
        per_thread: dict[str, int] = defaultdict(int)
        used = 0
        for r in rows:
            if len(items) >= k:
                break
            if per_doc[r["document_id"]] >= MAX_CHUNKS_PER_DOC or per_thread[r["thread"]] >= MAX_PER_THREAD:
                continue
            cost = estimate_tokens(r["text"])
            if items and used + cost > token_budget:
                continue
            per_doc[r["document_id"]] += 1
            per_thread[r["thread"]] += 1
            used += cost
            meta = r["meta"] or {}
            items.append(Item(chunk_id=r["id"], document_id=r["document_id"], title=r["title"], doc_type=r["doc_type"],
                              occurred_at=r["occurred_at"].isoformat() if r["occurred_at"] else None, text=r["text"],
                              score=round(r["score"], 5), why=r["why"],
                              ref={k2: meta[k2] for k2 in ("demo_id", "path", "filename") if meta.get(k2)}))
        return items

    async def _facts(self, query: str, entity_ids: list[str]) -> list[Fact]:
        facts: list[Fact] = []
        names = {e.id: e.name for e in self._matcher.entities.values()}
        if entity_ids:
            for r in await self.db.fetch(
                    "SELECT id, from_entity, type, to_entity FROM relations WHERE (from_entity = ANY(%s) "
                    "OR to_entity = ANY(%s)) AND valid_to IS NULL ORDER BY type LIMIT 8", (entity_ids, entity_ids)):
                facts.append(Fact(text=f"{names[r['from_entity']]} {r['type'].replace('_', ' ')} "
                                       f"{names[r['to_entity']]}", ref=f"relations:{r['id']}"))
            for r in await self.db.fetch(
                    "SELECT promiser, count(*) AS total, count(*) FILTER (WHERE (history->0->>'at')::timestamptz > due_at) "
                    "AS late FROM promises WHERE status = 'done' AND promiser = ANY(%s) GROUP BY promiser", (entity_ids,)):
                facts.append(Fact(text=f"{names[r['promiser']]} delivered {r['total'] - r['late']} of {r['total']} "
                                       f"past promises on time ({r['late']} late)", ref=f"promises:{r['promiser']}"))
            now = self.clock.now()
            for r in await self.db.fetch(
                    "SELECT id, title, starts_at FROM calendar_events WHERE attendees && %s AND starts_at >= %s "
                    "AND starts_at < %s ORDER BY starts_at LIMIT 3", (entity_ids, now, now + timedelta(days=7))):
                facts.append(Fact(text=f"Upcoming: {r['title']} on {r['starts_at'].astimezone(now.tzinfo):%a %d %b %H:%M}",
                                  ref=f"calendar_events:{r['id']}"))
        tsq = keyword_tsquery(query)
        if tsq:
            for r in await self.db.fetch(
                    "SELECT id, what, why, decided_at FROM decisions WHERE to_tsvector('english', what || ' ' || why || ' ' "
                    "|| array_to_string(alternatives_rejected, ' ')) @@ to_tsquery('english', %s) "
                    "ORDER BY ts_rank_cd(to_tsvector('english', what || ' ' || why), to_tsquery('english', %s)) DESC "
                    "LIMIT 2", (tsq, tsq)):
                facts.append(Fact(text=f"Decision ({r['decided_at']:%d %b %Y}): {r['what']} Why: {r['why']}",
                                  ref=f"decisions:{r['id']}"))
        return facts

    async def _log(self, pack: ContextPack, agent: str, scope_entities: list[str], scope_docs: list[str]) -> None:
        await self.db.execute(
            "INSERT INTO recall_log (id, agent, strategy, query, entity_ids, scope_docs, returned, facts, stats, at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (new_id("recall"), agent, pack.strategy, pack.query, [e["id"] for e in pack.entities], scope_docs,
             Jsonb([{"chunk_id": i.chunk_id, "document_id": i.document_id, "score": i.score, "why": i.why}
                    for i in pack.items]),
             Jsonb([f.model_dump() for f in pack.facts]), Jsonb({**pack.stats, "scope_entities": scope_entities}),
             self.clock.now()))


def _ms(t0: float) -> float:
    return (time.monotonic() - t0) * 1000
