"""Ingestion: RawDocs -> sources, emails, documents, entity mentions, chunks with embeddings, events.

Idempotent: a source with the same location and content hash is skipped, so re-running ingestion only
processes what is new. Entity linking is plain code (names, aliases, addresses, domains); the model
is only used for embeddings."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from psycopg.types.json import Jsonb

from omnitrix.core.clock import Clock
from omnitrix.core.db import Database
from omnitrix.core.events import EventBus, make_event
from omnitrix.core.ids import new_id

from .connectors import RawDoc
from .text import EntityMatcher, chunk_text, vector_literal

Embedder = Callable[[list[str]], Awaitable[list[list[float]]]]
EMBED_BATCH = 32
SOURCE_EVENT = {"email": "email.received", "file": "file.added", "obsidian_note": "note.changed",
                "manual": "file.added"}


@dataclass
class _Doc:
    id: str
    source_id: str
    title: str
    doc_type: str
    text: str
    occurred_at: object
    meta: dict
    header: str
    mentions: set[tuple[str, str]] = field(default_factory=set)
    base_entities: set[str] = field(default_factory=set)   # added to every chunk (e.g. the sender)


@dataclass
class IngestStats:
    seen: int = 0
    new_sources: int = 0
    skipped: int = 0
    documents: int = 0
    chunks: int = 0
    mentions: int = 0
    links: int = 0
    embed_ms: int = 0
    total_ms: int = 0


async def load_matcher(db: Database) -> EntityMatcher:
    return EntityMatcher(await db.fetch("SELECT id, name, type, aliases, details FROM entities"))


class Ingestor:
    def __init__(self, db: Database, embed: Embedder, clock: Clock, bus: EventBus | None = None):
        self.db = db
        self.embed = embed
        self.clock = clock
        self.bus = bus or EventBus(db)

    async def ingest(self, connectors: list) -> IngestStats:
        t0 = time.monotonic()
        stats = IngestStats()
        matcher = await load_matcher(self.db)
        docs: list[_Doc] = []
        emails: list[tuple[RawDoc, str]] = []           # (raw, document_id) for reply links

        async with self.db.connection() as conn:
            for connector in connectors:
                async for raw in connector.fetch():
                    stats.seen += 1
                    async with conn.transaction():
                        source = await (await conn.execute(
                            "INSERT INTO sources (id, type, location, content_hash, received_at, processed_at, meta) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (location, content_hash) DO NOTHING RETURNING id",
                            (new_id("source"), raw.kind, raw.location, raw.content_hash, raw.received_at,
                             self.clock.now(), Jsonb(raw.meta)))).fetchone()
                        if source is None:
                            stats.skipped += 1
                            continue
                        stats.new_sources += 1
                        new_docs = await self._store(conn, raw, source["id"], matcher)
                        docs += new_docs
                        if raw.kind == "email":
                            emails.append((raw, new_docs[0].id))
                        await self._announce(conn, raw, source["id"], new_docs)

        stats.documents = len(docs)
        stats.mentions = sum(len(d.mentions) for d in docs)
        stats.embed_ms, stats.chunks = await self._chunk_and_embed(docs, matcher)
        stats.links = await self._link_replies(emails)
        stats.total_ms = int((time.monotonic() - t0) * 1000)
        return stats

    # ----------------------------------------------------------------------------------------- storing

    async def _store(self, conn, raw: RawDoc, source_id: str, matcher: EntityMatcher) -> list[_Doc]:
        meta = dict(raw.meta)
        email_id = None
        if raw.kind == "email":
            email_id = new_id("email")
            sender = matcher.for_address(raw.from_addr or "")
            # outgoing only when the sender is the user's own address (colleagues share the domain)
            direction = "out" if any(matcher.is_self(eid) for eid, how in sender if how == "address") else "in"
            await conn.execute(
                "INSERT INTO emails (id, source_id, message_id, thread_id, in_reply_to, direction, from_addr, "
                "to_addrs, cc_addrs, subject, body_text, received_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (message_id) DO NOTHING",
                (email_id, source_id, raw.message_id, (raw.references or [raw.message_id])[0], raw.in_reply_to,
                 direction, raw.from_addr, [a for _, a in raw.to], [a for _, a in raw.cc], raw.title, raw.text,
                 raw.received_at))
            meta.update(email_id=email_id, from_name=raw.from_name, from_addr=raw.from_addr)

        header = self._header(raw)
        doc = _Doc(new_id("document"), source_id, raw.title, raw.doc_type, raw.text, raw.received_at, meta, header)
        self._link_entities(doc, raw, matcher)
        out = [doc]
        for att in raw.attachments:
            if not att.text:
                continue
            a = _Doc(new_id("document"), source_id, att.filename, "attachment", att.text, raw.received_at,
                     {"filename": att.filename, "email_id": email_id, "parent_document": doc.id,
                      "demo_id": meta.get("demo_id")},
                     f"attachment {att.filename} | to email '{raw.title}' | {raw.received_at:%d %b %Y} | "
                     f"from {raw.from_name}")
            a.mentions = {(eid, "text") for eid in matcher.find(att.text)} | {
                (eid, how) for eid, how in matcher.for_address(raw.from_addr or "")}
            a.base_entities = {eid for eid, _ in matcher.for_address(raw.from_addr or "")}
            out.append(a)

        for d in out:
            await conn.execute(
                "INSERT INTO documents (id, source_id, title, doc_type, full_text, occurred_at, meta) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (d.id, d.source_id, d.title, d.doc_type, d.text, d.occurred_at, Jsonb(d.meta)))
            for eid, how in sorted(d.mentions):
                await conn.execute("INSERT INTO mentions (document_id, entity_id, how) VALUES (%s,%s,%s) "
                                   "ON CONFLICT DO NOTHING", (d.id, eid, how))
        for a in out[1:]:
            await conn.execute("INSERT INTO document_links (from_doc, to_doc, type) VALUES (%s,%s,'attachment_of')",
                               (a.id, doc.id))
        return out

    @staticmethod
    def _header(raw: RawDoc) -> str:
        when = f"{raw.received_at:%a %d %b %Y}"
        if raw.kind == "email":
            return f"email '{raw.title}' | {when} | from {raw.from_name} <{raw.from_addr}>"
        return f"{raw.doc_type} '{raw.title}' | {when}"

    @staticmethod
    def _link_entities(doc: _Doc, raw: RawDoc, matcher: EntityMatcher) -> None:
        if raw.kind == "email":
            sender = matcher.for_address(raw.from_addr or "")
            doc.mentions |= {(eid, "sender" if how == "address" else "domain") for eid, how in sender}
            doc.base_entities |= {eid for eid, _ in sender}
            for _, addr in raw.to + raw.cc:
                doc.mentions |= {(eid, "recipient") for eid, _ in matcher.for_address(addr)}
            doc.mentions |= {(eid, "text") for eid in matcher.find(f"{raw.title}\n{raw.text}")}
        else:
            doc.mentions |= {(eid, "text") for eid in matcher.find(f"{raw.title}\n{raw.text}")}
            if raw.frontmatter:
                fm_text = " ".join(str(v) for v in raw.frontmatter.values())
                doc.mentions |= {(eid, "frontmatter") for eid in matcher.find(fm_text)}
                doc.base_entities |= {eid for eid in matcher.find(fm_text)}
        doc.base_entities |= {eid for eid in matcher.find(raw.title)}

    # -------------------------------------------------------------------------------- chunks + vectors

    async def _chunk_and_embed(self, docs: list[_Doc], matcher: EntityMatcher) -> tuple[int, int]:
        rows = []
        for d in docs:
            for i, piece in enumerate(chunk_text(d.text)):
                entities = sorted(set(matcher.find(piece)) | d.base_entities)
                rows.append((new_id("chunk"), d.id, i, piece, entities, d.header))
        t0 = time.monotonic()
        vectors: list[list[float]] = []
        for i in range(0, len(rows), EMBED_BATCH):
            vectors += await self.embed([f"{r[5]}\n{r[3]}" for r in rows[i:i + EMBED_BATCH]])
        embed_ms = int((time.monotonic() - t0) * 1000)
        async with self.db.connection() as conn, conn.transaction():
            for (cid, did, pos, text, entities, header), vec in zip(rows, vectors, strict=True):
                await conn.execute(
                    "INSERT INTO chunks (id, document_id, position, text, context, embedding, entity_ids) "
                    "VALUES (%s,%s,%s,%s,%s,%s::vector,%s)", (cid, did, pos, text, header, vector_literal(vec), entities))
        return embed_ms, len(rows)

    async def _link_replies(self, emails: list[tuple[RawDoc, str]]) -> int:
        links = 0
        async with self.db.connection() as conn:
            for raw, doc_id in emails:
                if not raw.in_reply_to:
                    continue
                parent = await (await conn.execute(
                    "SELECT d.id FROM emails e JOIN documents d ON d.meta->>'email_id' = e.id "
                    "WHERE e.message_id = %s AND d.doc_type = 'email'", (raw.in_reply_to,))).fetchone()
                if parent:
                    await conn.execute("INSERT INTO document_links (from_doc, to_doc, type) VALUES (%s,%s,'reply_to') "
                                       "ON CONFLICT DO NOTHING", (doc_id, parent["id"]))
                    links += 1
        return links

    # ------------------------------------------------------------------------------------------ events

    async def _announce(self, conn, raw: RawDoc, source_id: str, docs: list[_Doc]) -> None:
        first = make_event(SOURCE_EVENT[raw.kind], emitted_by="ingestion", clock=self.clock,
                           idempotency_key=f"{raw.kind}:{raw.location}:{raw.content_hash}",
                           subject=("source", source_id), payload={"source_id": source_id, "title": raw.title})
        await self.bus.publish(first, conn)
        for d in docs:
            await self.bus.publish(make_event("document.ingested", emitted_by="ingestion", clock=self.clock,
                                              caused_by=first, subject=("document", d.id),
                                              idempotency_key=f"document.ingested:{d.id}",
                                              payload={"document_id": d.id, "doc_type": d.doc_type}), conn)
