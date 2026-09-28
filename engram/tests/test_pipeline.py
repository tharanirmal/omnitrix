"""Ingest -> index -> search against a real (throwaway) Postgres database, with a fake embedder."""
import random
from datetime import UTC, datetime

import pytest

from engram import index as idx
from engram.db import connect
from engram.labels import filed
from engram.sources.enron import Message, owner_addresses
from engram.store import ingest_messages, rederive

from .conftest import fake_embed

pytestmark = pytest.mark.db
OWNER = "vince.kaminski@enron.com"


def msg(ref: str, sender: str, to: str, subject: str, body: str, day: int) -> Message:
    return Message(ref, "/".join(ref.split("/")[1:-1]), datetime(2000, 10, day, 9, tzinfo=UTC), sender, (to,), (),
                   subject, body)


INTERVIEW = "Vince, the candidates for the research group interviews are confirmed for Friday."
MESSAGES = [
    msg("v/inbox/1.", "shirley.crenshaw@enron.com", OWNER, "Interview schedule", INTERVIEW, 2),
    msg("v/all_documents/7.", "shirley.crenshaw@enron.com", OWNER, "Interview schedule", INTERVIEW, 2),  # a copy
    msg("v/sent/3.", OWNER, "shirley.crenshaw@enron.com", "Re: Interview schedule",
        f"Thanks, Shirley.\n\n-----Original Message-----\nFrom: Crenshaw, Shirley\nSent: Monday\n\n{INTERVIEW}", 3),
    msg("v/projects/weather/4.", "joe.hrgovcic@enron.com", OWNER, "Weather derivatives model",
        "The temperature option pricing model is ready for review. It uses heating degree days.", 4),
    msg("v/resumes/5.", "recruiter@agency.com", OWNER, "Quant analyst CV", "Attached is the CV of a PhD analyst.", 1),
]


@pytest.fixture(scope="module")
def ingested(db_url):
    with connect(db_url) as conn:
        stats = ingest_messages(conn, MESSAGES, {OWNER})
        conn.commit()
        idx.refresh_stats(conn)
    return db_url, stats


def test_copies_collapse_and_every_location_is_kept(ingested):
    url, stats = ingested
    assert (stats.messages, stats.new_items, stats.new_refs) == (5, 4, 5)
    with connect(url) as conn:
        folders = conn.execute("SELECT array_agg(r.folder ORDER BY r.folder) AS f FROM item_refs r JOIN items i "
                               "ON i.id = r.item_id WHERE i.subject = 'Interview schedule'").fetchone()["f"]
    assert folders == ["all_documents", "inbox"]


def test_direction_and_quoted_history(ingested):
    url, _ = ingested
    with connect(url) as conn:
        sent = conn.execute("SELECT i.body, i.quoted, i.direction, i.thread_key, c.text FROM items i "
                            "JOIN chunks c ON c.item_id = i.id WHERE i.subject LIKE 'Re:%'").fetchone()
    assert sent["direction"] == "out" and sent["thread_key"] == "interview schedule"
    assert sent["body"] == "Thanks, Shirley." and sent["quoted"].startswith("-----Original Message-----")
    assert "candidates" in sent["text"]          # a short reply is indexed with the context it answers


def test_ingest_is_idempotent(ingested):
    url, _ = ingested
    with connect(url) as conn:
        again = ingest_messages(conn, MESSAGES, {OWNER})
    assert (again.new_items, again.new_refs, again.chunks) == (0, 0, 0)


def test_keyword_and_hybrid_search_with_filters(ingested):
    url, _ = ingested
    with connect(url) as conn:
        assert idx.search(conn, None, "temperature pricing")[0].subject == "Weather derivatives model"
        assert idx.embed_pending(conn, fake_embed, batch=2) == 4
        idx.ensure_ann_index(conn)
        hits = idx.search(conn, fake_embed, "heating degree days model")
        assert hits[0].subject == "Weather derivatives model" and any("meaning" in w for w in hits[0].why)
        assert {h.subject for h in idx.search(conn, fake_embed, "interview", people=["crenshaw"])} == \
            {"Interview schedule", "Re: Interview schedule"}
        assert [h.subject for h in idx.search(conn, fake_embed, "interview", direction="out")] == \
            ["Re: Interview schedule"]
        assert idx.search(conn, fake_embed, "interview", since=datetime(2000, 10, 4, tzinfo=UTC),
                          until=datetime(2000, 10, 5, tzinfo=UTC))[0].subject == "Weather derivatives model"


def test_filed_labels_come_from_the_owners_own_folders(ingested):
    url, _ = ingested
    with connect(url) as conn:
        examples = filed(conn, n=10, rng=random.Random(0))
    assert sorted(e.label for e in examples) == ["projects/weather", "resumes"]          # not inbox or sent
    assert examples[0].question.labels == ("projects/weather", "resumes")


def test_rederive_resplits_items_after_a_parser_fix(ingested):
    url, _ = ingested
    with connect(url) as conn:
        item = conn.execute("SELECT id FROM items WHERE subject = 'Quant analyst CV'").fetchone()["id"]
        # what the old parser stored: a lone '>From' line mistaken for the start of quoted history
        conn.execute("UPDATE items SET body = 'Attached is the CV.', quoted = '>From our PhD programme, top of class.' "
                     "WHERE id = %s", (item,))
        conn.execute("INSERT INTO memory_scans (item_id, kinds) VALUES (%s, '{decision}')", (item,))
        conn.execute("INSERT INTO beliefs (kind, actor, statement, valid, item_id, quote, confidence) VALUES "
                     "('decision', 'x', 'read from the old text', tstzrange(now(), NULL), %s, 'q', 0.9)", (item,))
        assert rederive(conn) == 1
        assert conn.execute("SELECT count(*) AS n FROM memory_scans WHERE item_id = %s", (item,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM current_beliefs WHERE item_id = %s",
                            (item,)).fetchone()["n"] == 0                   # withdrawn, read again next build
        row = conn.execute("SELECT body, quoted FROM items WHERE id = %s", (item,)).fetchone()
        chunks = conn.execute("SELECT text, embedding FROM chunks WHERE item_id = %s", (item,)).fetchall()
        assert rederive(conn) == 0                                   # stable once re-derived
    assert row["quoted"] == "" and ">From our PhD programme" in row["body"]
    assert len(chunks) == 1 and "PhD programme" in chunks[0]["text"] and chunks[0]["embedding"] is None


def test_owner_addresses_come_from_sent_folders():
    mail = [msg(f"v/sent/{i}.", OWNER, "x@enron.com", "s", "b", 1) for i in range(3)]
    mail.append(msg("v/inbox/9.", "someone@enron.com", OWNER, "s", "b", 1))
    assert owner_addresses(mail, min_sent=2) == {OWNER}


def test_retrieval_benchmark_finds_gold_items(ingested):
    from engram.evaluate import retrieval
    from engram.sources.enronqa import QA

    url, _ = ingested
    qas = [QA("q1", "v/projects/weather/4.", "Which model uses heating degree days?", "the option model", ()),
           QA("q2", "v/inbox/1.", "When are the research group interviews?", "Friday", ()),
           QA("q3", "v/nowhere/9.", "Not in the brain?", "-", ())]
    with connect(url) as conn:
        idx.embed_pending(conn, fake_embed)
        report = retrieval(conn, fake_embed, qas, 10, random.Random(0))
    assert report["questions"] == 2                                         # only answerable questions count
    for scores in report["variants"].values():
        assert scores["recall@1"] <= scores["recall@5"] <= scores["recall@10"]
    assert report["variants"]["hybrid (engram)"]["recall@1"] == 1.0
