"""Writing messages into the brain. Identical copies collapse into one item, every original location is kept,
and each new item is split into retrieval chunks. Idempotent: re-running only adds what is new. When the parser
improves, `rederive` re-splits stored items in place (ids are kept), so derived data can always be rebuilt."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import psycopg

from .sources.enron import Message
from .text import chunk, content_hash, header, split_quoted, thread_key

SHORT_BODY = 200        # a message shorter than this is mostly its quoted/forwarded context ...
CONTEXT_CHARS = 1500    # ... so this much of that context is indexed with it


@dataclass
class IngestStats:
    messages: int = 0
    new_items: int = 0
    new_refs: int = 0
    chunks: int = 0


def ingest_messages(conn: psycopg.Connection, messages: Sequence[Message], owner_addrs: set[str],
                    source: str = "enron", kind: str = "email") -> IngestStats:
    stats = IngestStats(messages=len(messages))
    refs = [m.ref for m in messages]
    known = {r["ref"] for r in conn.execute("SELECT ref FROM item_refs WHERE ref = ANY(%s)", (refs,))}

    groups: dict[str, list[Message]] = {}
    for m in messages:
        if m.ref not in known:
            # recipients are left out on purpose: the same email kept in several folders must collapse
            key = content_hash(m.from_addr, m.sent_at.isoformat() if m.sent_at else "", m.subject, m.body)
            groups.setdefault(key, []).append(m)
    ids = {r["content_hash"]: r["id"] for r in
           conn.execute("SELECT id, content_hash FROM items WHERE content_hash = ANY(%s)", (list(groups),))}
    new = {h: split_quoted(ms[0].body) for h, ms in groups.items() if h not in ids}

    with conn.cursor().copy("COPY items (source, kind, content_hash, sent_at, from_addr, to_addrs, cc_addrs, subject, "
                            "body, quoted, thread_key, direction) FROM STDIN") as cp:
        for h, (body, quoted) in new.items():
            m = groups[h][0]
            cp.write_row((source, kind, h, m.sent_at, m.from_addr, list(m.to_addrs), list(m.cc_addrs), m.subject,
                          body, quoted, thread_key(m.subject), "out" if m.from_addr in owner_addrs else "in"))
    ids |= {r["content_hash"]: r["id"] for r in
            conn.execute("SELECT id, content_hash FROM items WHERE content_hash = ANY(%s)", (list(new),))}

    with conn.cursor().copy("COPY item_refs (ref, item_id, folder) FROM STDIN") as cp:
        for h, ms in groups.items():
            for m in ms:
                cp.write_row((m.ref, ids[h], m.folder))
                stats.new_refs += 1

    rows = [row for h, (body, quoted) in new.items() for row in chunk_rows(
        ids[h], groups[h][0].sent_at, groups[h][0].from_addr, [*groups[h][0].to_addrs, *groups[h][0].cc_addrs],
        groups[h][0].subject, body, quoted)]
    _copy_chunks(conn, rows)
    stats.new_items, stats.chunks = len(new), len(rows)
    return stats


def rederive(conn: psycopg.Connection) -> int:
    """Re-split every item with the current parser; rebuild the chunks of items whose split changed (their
    vectors are cleared, so `engram index` re-embeds just those) and have memory read them again. Returns how many
    items changed."""
    changed: list[tuple] = []
    for r in conn.execute("SELECT id, sent_at, from_addr, to_addrs, cc_addrs, subject, body, quoted FROM items"):
        body, quoted = split_quoted(f"{r['body']}\n\n{r['quoted']}")
        if (body, quoted) != (r["body"], r["quoted"]):
            changed.append((r, body, quoted))
    for r, body, quoted in changed:
        conn.execute("UPDATE items SET body = %s, quoted = %s WHERE id = %s", (body, quoted, r["id"]))
    ids = [r["id"] for r, _, _ in changed]
    conn.execute("DELETE FROM chunks WHERE item_id = ANY(%s)", (ids,))
    # what memory read from the old text is withdrawn (kept as history) and the item is read again next build
    conn.execute("UPDATE beliefs SET recorded = tstzrange(lower(recorded), now()) "
                 "WHERE item_id = ANY(%s) AND upper_inf(recorded)", (ids,))
    conn.execute("DELETE FROM memory_scans WHERE item_id = ANY(%s)", (ids,))
    _copy_chunks(conn, [row for r, body, quoted in changed for row in chunk_rows(
        r["id"], r["sent_at"], r["from_addr"], [*r["to_addrs"], *r["cc_addrs"]], r["subject"], body, quoted)])
    return len(changed)


def chunk_rows(item_id: int, sent_at: datetime | None, sender: str, recipients: list[str], subject: str,
               body: str, quoted: str) -> list[tuple[int, int, str, str]]:
    """(item_id, ord, header, text) for one item; a short message is indexed with the context it answers."""
    text = body if len(body) >= SHORT_BODY or not quoted else f"{body}\n\n{quoted[:CONTEXT_CHARS]}".strip()
    head = header(sent_at, sender, recipients, subject)
    return [(item_id, i, head, piece) for i, piece in enumerate(chunk(text) or [""])]


def _copy_chunks(conn: psycopg.Connection, rows: list[tuple[int, int, str, str]]) -> None:
    with conn.cursor().copy("COPY chunks (item_id, ord, header, text) FROM STDIN") as cp:
        for row in rows:
            cp.write_row(row)
    if rows:                                            # keyword postings for just these chunks (sql/007)
        conn.execute("INSERT INTO postings (lexeme, chunk_id, tf, len) "
                     "SELECT t.lexeme, c.id, cardinality(t.positions), "
                     "       sum(cardinality(t.positions)) OVER (PARTITION BY c.id) "
                     "FROM chunks c, unnest(c.tsv) t WHERE c.item_id = ANY(%s) "
                     "AND NOT EXISTS (SELECT 1 FROM postings p WHERE p.chunk_id = c.id)",
                     (sorted({r[0] for r in rows}),))
