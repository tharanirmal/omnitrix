"""Obsidian two-way memory: export, then every kind of owner action flows back."""
from datetime import UTC, datetime

import pytest

from engram.db import connect
from engram.sources.enron import Message
from engram.store import ingest_messages
from engram.vault import queue_review, sync

pytestmark = pytest.mark.db
OWNER = "vince.kaminski@enron.com"


def test_two_way_sync(db_url, tmp_path):
    with connect(db_url) as conn:
        ingest_messages(conn, [Message("v/inbox/1.", "inbox", datetime(2001, 5, 1, 15, tzinfo=UTC),
                                       "shirley.crenshaw@enron.com", (OWNER,), (), "Offsite",
                                       "I will book the room for the offsite. We decided on Galveston.")], {OWNER})
        item = conn.execute("SELECT id FROM items").fetchone()["id"]
        for kind, stmt in (("commitment", "Shirley will book the room"), ("decision", "The offsite is in Galveston")):
            conn.execute("INSERT INTO beliefs (kind, actor, other, statement, valid, item_id, quote, confidence) "
                         "VALUES (%s, 'shirley crenshaw', 'vince', %s, tstzrange(now(), NULL), %s, 'q', 0.9)",
                         (kind, stmt, item))
        s = sync(conn, tmp_path)
        assert s.written == 2 and (tmp_path / "engram.base").exists()
        notes = {p.parent.name: p for p in tmp_path.rglob("*.md") if p.parent.name in ("Commitments", "Decisions")}
        assert "[[Shirley Crenshaw]]" in notes["Commitments"].read_text() and (tmp_path / "People").exists()
        assert sync(conn, tmp_path).written == 0                                     # idempotent

        text = notes["Commitments"].read_text()                                     # the owner edits...
        notes["Commitments"].write_text(text.replace("Shirley will book the room", "Shirley will book the big room")
                                        .replace("status: open", "status: done"))
        notes["Decisions"].unlink()                                                  # ...deletes...
        (tmp_path / "Commitments" / "Call the caterer.md").write_text("I will call the caterer.\n")   # ...adds...
        (tmp_path / "Ideas.md").write_text("Maybe a pricing seminar in the spring.\n")               # ...writes
        s = sync(conn, tmp_path)
        assert (s.edited, s.status_changed, s.deleted, s.created, s.notes) == (1, 1, 1, 1, 1)
        current = {r["statement"]: r for r in conn.execute("SELECT statement, author, status, supersedes "
                                                            "FROM current_beliefs")}
        assert set(current) == {"Shirley will book the big room", "I will call the caterer."}
        assert current["Shirley will book the big room"]["author"] == "owner"
        assert current["Shirley will book the big room"]["supersedes"] is not None
        verdicts = {r["value"] for r in conn.execute("SELECT value FROM labels WHERE question = 'belief_ok'")}
        assert verdicts == {"corrected", "no"}
        assert "big room" in notes["Commitments"].read_text()                        # re-rendered, owner's words
        assert conn.execute("SELECT count(*) AS n FROM items WHERE source = 'obsidian'").fetchone()["n"] == 2

        queue_review(conn, tmp_path, [{"id": item, "subject": "Offsite", "from_addr": "x", "body": "b", "p": 0.5,
                                       "sent_at": None}])
        review = next((tmp_path / "Review").glob("*.md"))
        review.write_text(review.read_text().replace("verdict: ''", "verdict: keep"))
        assert sync(conn, tmp_path).reviewed == 1 and not review.exists()
        assert conn.execute("SELECT value FROM labels WHERE question = 'remember'").fetchone()["value"] == "yes"


def test_editing_a_note_engram_has_since_superseded(db_url, tmp_path):
    with connect(db_url) as conn:
        ingest_messages(conn, [Message("v/inbox/9.", "inbox", datetime(2001, 6, 1, tzinfo=UTC), "a@enron.com",
                                       (OWNER,), (), "Review", "I will send the review by Friday.")], {OWNER})
        item = conn.execute("SELECT id FROM items WHERE subject = 'Review'").fetchone()["id"]
        old = conn.execute("INSERT INTO beliefs (kind, actor, other, statement, valid, item_id, quote, confidence) "
                           "VALUES ('commitment', 'ann', 'vince', 'Ann will send the review', "
                           "tstzrange(now(), NULL), %s, 'q', 0.9) RETURNING id", (item,)).fetchone()["id"]
        sync(conn, tmp_path)
        note = next((tmp_path / "Commitments").glob("*review*.md"))
        # a later email: engram supersedes the belief the note was written from
        conn.execute("UPDATE beliefs SET recorded = tstzrange(lower(recorded), now()) WHERE id = %s", (old,))
        conn.execute("INSERT INTO beliefs (kind, actor, other, statement, valid, item_id, quote, confidence, "
                     "supersedes) VALUES ('commitment', 'ann', 'vince', 'Ann will send the review on Monday', "
                     "tstzrange(now(), NULL), %s, 'q', 0.9, %s)", (item, old))
        conn.commit()
        note.write_text(note.read_text().replace("Ann will send the review", "Ann will send the final review")
                        .replace("status: open", "status: In Progress"))          # an invalid status too
        s = sync(conn, tmp_path)
        chain = conn.execute("SELECT statement, author, status FROM current_beliefs WHERE actor = 'ann'").fetchall()
        assert s.edited == 1 and s.skipped == 0
        assert [(r["statement"], r["author"], r["status"]) for r in chain] == \
            [("Ann will send the final review", "owner", "open")]                   # one current belief, not two
