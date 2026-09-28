"""Agent log: every brain recall, read back from recall_log (plus the documents and chunks it returned).

The log stores chunk ids; titles, types, source ids and text are joined in from chunks + documents when an
entry is opened. A chunk that has since been deleted (e.g. scale-test documents removed) is shown as missing.
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg

from omnitrix.brain.text import estimate_tokens
from omnitrix.core.db import Database

CHANNEL = "omnitrix_recall"          # migrations/003: a trigger on recall_log NOTIFYs each new row's id
SOURCE_KEYS = ("demo_id", "path", "filename")
TIMING_KEYS = ("entities_ms", "scope_ms", "embed_ms", "vector_ms", "keyword_ms", "facts_ms")


def _label(at: datetime | None, tz: ZoneInfo) -> str:
    return f"{at.astimezone(tz):%a %d %b %H:%M:%S}" if at else ""


def source_ref(meta: dict | None) -> dict | None:
    """The id a person would recognise: demo email id, vault path or file name."""
    meta = meta or {}
    for key in SOURCE_KEYS:
        if meta.get(key):
            return {"kind": key, "value": meta[key]}
    return None


def summary(row: dict, tz: ZoneInfo) -> dict:
    st = row["stats"] or {}
    return {
        "id": row["id"], "agent": row["agent"], "strategy": row["strategy"], "query": row["query"],
        "at": row["at"].astimezone(tz).isoformat(), "at_label": _label(row["at"], tz),
        "returned_chunks": st.get("returned_chunks"), "facts": st.get("facts"),
        "returned_tokens": st.get("returned_tokens"), "total_ms": st.get("total_ms"),
        "scoped": st.get("scoped"), "share_searched": st.get("share_searched"),
    }


async def list_recalls(db: Database, tz: ZoneInfo, *, agent: str | None = None, strategy: str | None = None,
                       since: datetime | None = None, until: datetime | None = None, before: str | None = None,
                       limit: int = 100) -> list[dict]:
    """Newest first by demo-clock time. `before` is the id of the last entry already shown (keyset paging:
    a frozen demo clock gives many entries the same `at`, so recorded_at breaks the tie)."""
    rows = await db.fetch(
        "SELECT id, agent, strategy, query, at, stats FROM recall_log "
        "WHERE (%(agent)s::text IS NULL OR agent = %(agent)s) "
        "AND (%(strategy)s::text IS NULL OR strategy = %(strategy)s) "
        "AND (%(since)s::timestamptz IS NULL OR at >= %(since)s) "
        "AND (%(until)s::timestamptz IS NULL OR at <= %(until)s) "
        "AND (%(before)s::text IS NULL OR (at, recorded_at) < "
        "     (SELECT at, recorded_at FROM recall_log WHERE id = %(before)s)) "
        "ORDER BY at DESC, recorded_at DESC LIMIT %(limit)s",
        {"agent": agent, "strategy": strategy, "since": since, "until": until, "before": before, "limit": limit})
    return [summary(r, tz) for r in rows]


async def get_summary(db: Database, tz: ZoneInfo, recall_id: str) -> dict | None:
    row = await db.fetchrow("SELECT id, agent, strategy, query, at, stats FROM recall_log WHERE id = %s", (recall_id,))
    return summary(row, tz) if row else None


async def agents_and_strategies(db: Database) -> dict:
    row = await db.fetchrow("SELECT coalesce(array_agg(DISTINCT agent), '{}') AS agents, "
                            "coalesce(array_agg(DISTINCT strategy), '{}') AS strategies FROM recall_log")
    return {"agents": sorted(row["agents"]), "strategies": sorted(row["strategies"])}


async def get_recall(db: Database, tz: ZoneInfo, recall_id: str) -> dict | None:
    """One log entry with everything the detail panel shows."""
    row = await db.fetchrow("SELECT * FROM recall_log WHERE id = %s", (recall_id,))
    if row is None:
        return None
    st = row["stats"] or {}
    scope_entities = st.get("scope_entities") or []
    names = {e["id"]: e for e in await db.fetch(
        "SELECT id, name, type FROM entities WHERE id = ANY(%s)", (list(row["entity_ids"]) + scope_entities,))}

    def entity(eid: str) -> dict:
        return names.get(eid) or {"id": eid, "name": eid, "type": "unknown"}

    returned = row["returned"] or []
    found = {c["chunk_id"]: c for c in await db.fetch(
        "SELECT c.id AS chunk_id, c.document_id, c.position, c.text, d.title, d.doc_type, d.occurred_at, d.meta "
        "FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.id = ANY(%s)",
        ([r["chunk_id"] for r in returned],))}
    chunks = []
    for rank, r in enumerate(returned, 1):
        c = found.get(r["chunk_id"])
        base = {"rank": rank, "chunk_id": r["chunk_id"], "document_id": r["document_id"], "score": r.get("score"),
                "why": r.get("why", [])}
        if c is None:
            chunks.append({**base, "missing": True})
            continue
        chunks.append({**base, "missing": False, "title": c["title"], "doc_type": c["doc_type"],
                       "position": c["position"], "occurred_at": _label(c["occurred_at"], tz) or None,
                       "source": source_ref(c["meta"]), "from": (c["meta"] or {}).get("from_name"),
                       "text": c["text"], "tokens": estimate_tokens(c["text"])})

    corpus_docs = st.get("corpus_documents") or 0
    scope_docs = st.get("scope_documents", corpus_docs)
    return {
        **summary(row, tz),
        "recorded_at": row["recorded_at"].isoformat(),
        "entities": [entity(e) for e in row["entity_ids"]],
        "scope_entities": [entity(e) for e in scope_entities if e not in row["entity_ids"]],
        "search": {
            "scoped": bool(st.get("scoped")), "fallback": bool(st.get("fallback")),
            "scope_documents": scope_docs, "corpus_documents": corpus_docs,
            "share_documents": round(scope_docs / corpus_docs, 4) if corpus_docs else None,
            "scope_chunks": st.get("scope_chunks"), "corpus_chunks": st.get("corpus_chunks"),
            "share_chunks": st.get("share_searched"), "candidates": st.get("candidates"),
        },
        "chunks": chunks,
        "facts": row["facts"] or [],
        "cost": {
            "returned_tokens": st.get("returned_tokens"), "corpus_tokens": st.get("corpus_tokens"),
            "share_returned": st.get("share_returned"), "total_ms": st.get("total_ms"),
            "timings": {k: st[k] for k in TIMING_KEYS if k in st},
        },
    }


async def get_document(db: Database, tz: ZoneInfo, document_id: str) -> dict | None:
    doc = await db.fetchrow("SELECT id, title, doc_type, full_text, occurred_at, meta FROM documents WHERE id = %s",
                            (document_id,))
    if doc is None:
        return None
    meta = doc["meta"] or {}
    chunks = await db.fetch("SELECT id, position, text FROM chunks WHERE document_id = %s ORDER BY position",
                            (document_id,))
    parent = None
    if meta.get("parent_document"):
        parent = await db.fetchrow("SELECT id, title FROM documents WHERE id = %s", (meta["parent_document"],))
    return {"id": doc["id"], "title": doc["title"], "doc_type": doc["doc_type"], "full_text": doc["full_text"],
            "occurred_at": _label(doc["occurred_at"], tz) or None, "source": source_ref(meta),
            "from": meta.get("from_name"), "from_addr": meta.get("from_addr"), "parent": parent,
            "chunks": [{"id": c["id"], "position": c["position"], "text": c["text"]} for c in chunks]}


class RecallFeed:
    """One LISTEN connection shared by every open dashboard tab; each tab gets its own queue of new ids.

    Started on the first subscriber, reconnects if Postgres restarts."""

    def __init__(self, url: str):
        self.url = url
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._task: asyncio.Task | None = None
        self._listening = asyncio.Event()

    async def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        self._subscribers.add(queue)
        if self._task is None or self._task.done():
            self._listening.clear()
            self._task = asyncio.create_task(self._run())
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._listening.wait(), 5)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._subscribers.discard(queue)

    async def _run(self) -> None:
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(self.url, autocommit=True) as conn:
                    await conn.execute(f"LISTEN {CHANNEL}")
                    self._listening.set()
                    async for note in conn.notifies():
                        for queue in list(self._subscribers):
                            with contextlib.suppress(asyncio.QueueFull):     # a stalled tab just misses updates
                                queue.put_nowait(note.payload)
            except psycopg.OperationalError:
                self._listening.clear()
                await asyncio.sleep(2)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
