"""Obsidian as the brain's two-way memory (docs/research/round2-plan.md §B).

The vault holds one note per current belief (`Commitments/`, `Decisions/`, `Meetings/`), linked to `People/` and to
a read-only mirror of the source it came from (`Sources/`), plus `engram.base` for Obsidian's database views. A sync
imports first, then exports:

- the owner edits a belief's statement, due date or people → a belief they author supersedes it (history kept)
- the owner changes `status` → the belief's status changes
- the owner deletes a belief note → the belief is retracted, and that is a label the gate and extractor learn from
- the owner writes a new note in a belief folder → it becomes an owner item and an owner belief
- the owner sets `verdict: keep` or `drop` on a `Review/` note → a label for the memory gate
- any other note the owner writes → an item, so their own notes are searchable data

The owner is the authority: a file they changed is never overwritten. Postgres keeps every version."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import yaml

from .sources.enron import Message
from .store import ingest_messages

FOLDERS = {"commitment": "Commitments", "decision": "Decisions", "meeting": "Meetings"}
KIND_OF = {v: k for k, v in FOLDERS.items()}
MANAGED = (*FOLDERS.values(), "People", "Sources", "Review")
BASE = """filters:
  and:
    - 'engram == "belief"'
views:
  - type: table
    name: Open commitments
    filters:
      and:
        - 'kind == "commitment"'
        - 'status == "open"'
    order: [file.name, actor, other, due, confidence]
  - type: table
    name: Decisions
    filters:
      and:
        - 'kind == "decision"'
    order: [file.name, actor, other, confidence]
  - type: table
    name: Meetings
    filters:
      and:
        - 'kind == "meeting"'
    order: [file.name, actor, other, due]
"""
REVIEW_BASE = """filters:
  and:
    - 'engram == "review"'
views:
  - type: table
    name: Worth remembering?
    order: [file.name, from, gate_p, verdict]
"""


@dataclass
class SyncStats:
    edited: int = 0
    status_changed: int = 0
    deleted: int = 0
    created: int = 0
    reviewed: int = 0
    skipped: int = 0                    # notes that could not be read back; left as they are
    notes: int = 0
    written: int = 0
    removed: int = 0


def sync(conn: psycopg.Connection, vault: Path) -> SyncStats:
    vault.mkdir(parents=True, exist_ok=True)
    stats = SyncStats()
    _import(conn, vault, stats)
    _export(conn, vault, stats)
    conn.commit()
    return stats


# --------------------------------------------------------------------------------------------------- import

def _import(conn: psycopg.Connection, vault: Path, stats: SyncStats) -> None:
    tracked = {r["path"]: r for r in conn.execute("SELECT path, kind, ref_id, exported_hash FROM vault_files")}
    for rel, row in tracked.items():
        path = vault / rel
        try:
            with conn.transaction():                        # one note that cannot be read back blocks no other
                if row["kind"] == "belief":
                    if not path.exists():
                        _retract(conn, _current(conn, row["ref_id"]))
                        conn.execute("DELETE FROM vault_files WHERE path = %s", (rel,))
                        stats.deleted += 1
                    elif _hash(path.read_text()) != row["exported_hash"]:
                        _apply_edit(conn, rel, row["ref_id"], *_read(path), stats)
                elif row["kind"] == "review" and path.exists():
                    meta, _ = _read(path)
                    verdict = str(meta.get("verdict") or "").strip().lower()
                    if verdict in ("keep", "drop"):
                        conn.execute("INSERT INTO labels (question, subject, value, source) VALUES ('remember', %s, "
                                     "%s, 'human') ON CONFLICT (question, subject, source) DO UPDATE SET value = "
                                     "EXCLUDED.value", (f"item:{row['ref_id']}", "yes" if verdict == "keep" else "no"))
                        path.unlink()
                        conn.execute("DELETE FROM vault_files WHERE path = %s", (rel,))
                        stats.reviewed += 1
        except (psycopg.Error, OSError):
            stats.skipped += 1
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        if (rel in tracked and tracked[rel]["kind"] != "note") or rel.startswith("."):
            continue
        top = rel.split("/", 1)[0]
        meta, body = _read(path)
        if top in KIND_OF and not meta.get("id"):
            _create_belief(conn, rel, KIND_OF[top], meta, body, path)
            stats.created += 1
        elif top not in MANAGED:
            _ingest_note(conn, rel, path)
            stats.notes += 1


def _apply_edit(conn: psycopg.Connection, rel: str, belief_id: int, meta: dict[str, Any], body: str,
                stats: SyncStats) -> None:
    belief_id = _current(conn, belief_id)             # engram may have superseded it since the last sync
    b = conn.execute("SELECT * FROM beliefs WHERE id = %s", (belief_id,)).fetchone()
    if b is None:
        return
    status = str(meta.get("status") or "").strip().lower()
    status = status if status in ("open", "done", "dropped") else b["status"]
    if status != b["status"]:
        conn.execute("UPDATE beliefs SET status = %s WHERE id = %s AND upper_inf(recorded)", (status, belief_id))
        stats.status_changed += 1
    new = {"statement": _statement(body) or b["statement"], "actor": _unlink(meta.get("actor")) or b["actor"],
           "other": _unlink(meta.get("other")) if "other" in meta else b["other"], "due": _when(meta.get("due"))}
    old_due = b["due_at"].strftime("%Y-%m-%d %H:%M") if b["due_at"] else None
    new_due = new["due"].strftime("%Y-%m-%d %H:%M") if new["due"] else None
    if (new["statement"], new["actor"], new["other"], new_due) != (b["statement"], b["actor"], b["other"], old_due):
        conn.execute("UPDATE beliefs SET recorded = tstzrange(lower(recorded), now()) WHERE id = %s AND "
                     "upper_inf(recorded)", (belief_id,))
        row = conn.execute(
            "INSERT INTO beliefs (kind, actor, other, statement, due_at, when_text, status, valid, item_id, quote, "
            "confidence, supersedes, author, trust) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1.0, %s, 'owner', "
            "'owner') "
            "RETURNING id", (b["kind"], new["actor"], new["other"], new["statement"], new["due"], b["when_text"],
                             status, b["valid"], b["item_id"], b["quote"], belief_id)).fetchone()
        conn.execute("UPDATE vault_files SET ref_id = %s WHERE path = %s", (row["id"], rel))
        _label(conn, belief_id, "corrected")
        stats.edited += 1
    conn.execute("UPDATE vault_files SET exported_hash = '' WHERE path = %s", (rel,))   # re-render on export


def _current(conn: psycopg.Connection, belief_id: int) -> int:
    """The belief that now stands for `belief_id`: itself, or the latest one superseding it (an owner's edit of an
    old note corrects what the brain believes now, instead of forking history)."""
    for _ in range(100):
        nxt = conn.execute("SELECT id FROM beliefs WHERE supersedes = %s ORDER BY id DESC LIMIT 1",
                           (belief_id,)).fetchone()
        if nxt is None:
            return belief_id
        belief_id = nxt["id"]
    return belief_id


def _retract(conn: psycopg.Connection, belief_id: int) -> None:
    conn.execute("UPDATE beliefs SET recorded = tstzrange(lower(recorded), now()) WHERE id = %s AND "
                 "upper_inf(recorded)", (belief_id,))
    _label(conn, belief_id, "no")


def _label(conn: psycopg.Connection, belief_id: int, value: str) -> None:
    """The owner's verdict on a belief: 'no' (deleted) or 'corrected' (edited). Training data for the gate and
    the extractor."""
    conn.execute("INSERT INTO labels (question, subject, value, source) VALUES ('belief_ok', %s, %s, 'human') "
                 "ON CONFLICT (question, subject, source) DO UPDATE SET value = EXCLUDED.value",
                 (f"belief:{belief_id}", value))


def _create_belief(conn: psycopg.Connection, rel: str, kind: str, meta: dict[str, Any], body: str,
                   path: Path) -> None:
    item_id = _ingest_note(conn, rel, path)
    statement = _statement(body) or path.stem
    row = conn.execute(
        "INSERT INTO beliefs (kind, actor, other, statement, due_at, status, valid, item_id, quote, confidence, "
        "author, trust) VALUES (%s, %s, %s, %s, %s, %s, tstzrange(now(), NULL), %s, %s, 1.0, 'owner', 'owner') "
        "RETURNING id",
        (kind, _unlink(meta.get("actor")) or "owner", _unlink(meta.get("other")) or "", statement,
         _when(meta.get("due")), _status(meta.get("status")), item_id, statement)).fetchone()
    conn.execute("DELETE FROM vault_files WHERE path = %s", (rel,))
    conn.execute("INSERT INTO vault_files (path, kind, ref_id, exported_hash) VALUES (%s, 'belief', %s, '')",
                 (rel, row["id"]))


def _ingest_note(conn: psycopg.Connection, rel: str, path: Path) -> int:
    """An owner's note as an item (source 'obsidian'); unchanged notes are not read twice."""
    text = path.read_text()
    known = conn.execute("SELECT ref_id, exported_hash FROM vault_files WHERE path = %s", (rel,)).fetchone()
    if known and known["exported_hash"] == _hash(text):
        return known["ref_id"]
    when = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    msg = Message(f"obsidian/{rel}", "obsidian", when, "owner", (), (), path.stem, _read(path)[1] or text)
    ingest_messages(conn, [msg], {"owner"}, "obsidian", "note")
    item = conn.execute("SELECT item_id FROM item_refs WHERE ref = %s", (msg.ref,)).fetchone()["item_id"]
    conn.execute("INSERT INTO vault_files (path, kind, ref_id, exported_hash) VALUES (%s, 'note', %s, %s) "
                 "ON CONFLICT (path) DO UPDATE SET ref_id = EXCLUDED.ref_id, exported_hash = EXCLUDED.exported_hash",
                 (rel, item, _hash(text)))
    return item


# --------------------------------------------------------------------------------------------------- export

def _export(conn: psycopg.Connection, vault: Path, stats: SyncStats) -> None:
    beliefs = conn.execute("SELECT b.*, i.subject, i.sent_at, i.from_addr, i.body FROM current_beliefs b "
                           "JOIN items i ON i.id = b.item_id ORDER BY b.id").fetchall()
    files = {r["ref_id"]: r for r in conn.execute("SELECT * FROM vault_files WHERE kind = 'belief'")}
    current = {b["id"] for b in beliefs}
    for ref, f in files.items():                        # engram superseded or retracted it: the note goes
        if ref not in current:
            path = vault / f["path"]
            if path.exists() and _hash(path.read_text()) != f["exported_hash"]:
                continue                                # the owner changed it: kept, and still tracked
            if path.exists():
                path.unlink()
                stats.removed += 1
            conn.execute("DELETE FROM vault_files WHERE path = %s", (f["path"],))
    people: set[str] = set()
    for b in beliefs:
        source = _source_name(b)
        rel = files[b["id"]]["path"] if b["id"] in files else _free(vault, f"{FOLDERS[b['kind']]}/"
                                                                      f"{_day(b)} {_slug(b['statement'], 60)}.md")
        text = _render_belief(b, source)
        stats.written += _write(conn, vault, rel, "belief", b["id"], text)
        people |= {p for p in (b["actor"], b["other"]) if p}
        _write(conn, vault, f"Sources/{source}.md", "source", b["item_id"], _render_source(b))
    for p in sorted(people):
        _write(conn, vault, f"People/{_name(p)}.md", "person", 0, f"---\nengram: person\n---\n# {_name(p)}\n")
    for rel, text in (("engram.base", BASE), ("Review/review.base", REVIEW_BASE)):
        if not (vault / rel).exists():
            (vault / rel).parent.mkdir(parents=True, exist_ok=True)
            (vault / rel).write_text(text)


def queue_review(conn: psycopg.Connection, vault: Path, items: list[dict[str, Any]]) -> int:
    """Put items the gate is unsure about in `Review/` for the owner: `verdict: keep` or `drop` becomes a label."""
    n = 0
    for it in items:
        rel = f"Review/{_day(it)} {_slug(it['subject'] or 'untitled', 70)} (item {it['id']}).md"
        meta = {"engram": "review", "item": it["id"], "from": it["from_addr"], "gate_p": round(it["p"], 2),
                "verdict": ""}
        text = f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n{it['body'][:3000]}\n"
        n += _write(conn, vault, rel, "review", it["id"], text)
    conn.commit()
    return n


def _write(conn: psycopg.Connection, vault: Path, rel: str, kind: str, ref: int, text: str) -> int:
    """Write unless the owner has changed the file since engram last wrote it. Returns 1 if written."""
    path = vault / rel
    row = conn.execute("SELECT exported_hash FROM vault_files WHERE path = %s", (rel,)).fetchone()
    if path.exists():
        on_disk = _hash(path.read_text())
        if on_disk == _hash(text):
            return 0
        if row is None or (row["exported_hash"] and on_disk != row["exported_hash"]):
            return 0                                    # the owner's file: never overwritten
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    conn.execute("INSERT INTO vault_files (path, kind, ref_id, exported_hash) VALUES (%s, %s, %s, %s) ON CONFLICT "
                 "(path) DO UPDATE SET ref_id = EXCLUDED.ref_id, exported_hash = EXCLUDED.exported_hash, "
                 "synced_at = now()", (rel, kind, ref, _hash(text)))
    return 1


def _render_belief(b: dict[str, Any], source: str) -> str:
    meta = {"engram": "belief", "id": b["id"], "kind": b["kind"], "status": b["status"],
            "actor": f"[[{_name(b['actor'])}]]" if b["actor"] else "",
            "other": f"[[{_name(b['other'])}]]" if b["other"] else "",
            "due": b["due_at"].strftime("%Y-%m-%d %H:%M") if b["due_at"] else "",
            "confidence": round(float(b["confidence"]), 2), "author": b["author"], "source": f"[[{source}]]"}
    quote = "\n".join(f"> {line}" for line in b["quote"].splitlines())
    return f"---\n{yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)}---\n{b['statement']}\n\n{quote}\n"


def _render_source(b: dict[str, Any]) -> str:
    meta = {"engram": "source", "id": b["item_id"], "from": b["from_addr"],
            "date": b["sent_at"].strftime("%Y-%m-%d") if b["sent_at"] else ""}
    return f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n# {b['subject']}\n\n{b['body'][:4000]}\n"


# -------------------------------------------------------------------------------------------------- helpers

def _read(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), m.group(2)


def _statement(body: str) -> str:
    """The first paragraph of a note that is not a quote or a heading."""
    for para in re.split(r"\n\s*\n", body.strip()):
        para = para.strip()
        if para and not para.startswith((">", "#")):
            return " ".join(para.split())
    return ""


def _status(v: Any) -> str:
    s = str(v or "").strip().lower()
    return s if s in ("open", "done", "dropped") else "open"


def _unlink(v: Any) -> str:
    return re.sub(r"^\[\[(.*?)(\|.*)?\]\]$", r"\1", str(v or "").strip()).strip().lower()


def _when(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v).strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _name(s: str) -> str:
    s = s.strip()
    return _slug(s.title() if s == s.lower() and "@" not in s else s, 80)


def _slug(s: str, n: int) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|#^\[\]]', "", s)).strip()[:n].rstrip() or "untitled"


def _day(r: dict[str, Any]) -> str:
    return f"{r['sent_at']:%Y-%m-%d}" if r.get("sent_at") else "undated"


def _source_name(b: dict[str, Any]) -> str:
    return f"{_day(b)} {_slug(b['subject'] or 'untitled', 60)} (item {b['item_id']})"


def _free(vault: Path, rel: str) -> str:
    stem, k = rel[:-3], 2
    while (vault / rel).exists():
        rel, k = f"{stem} {k}.md", k + 1
    return rel


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
