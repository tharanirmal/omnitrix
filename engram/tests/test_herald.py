"""Herald: each role's cards, the routing rules, and the owner's taps going back to the role that asked."""
from datetime import UTC, datetime, timedelta

import pytest

from engram import herald
from engram.db import connect
from engram.judge import verify_ledger
from engram.sources.enron import Message
from engram.store import ingest_messages

pytestmark = pytest.mark.db

OWNER = "vince.kaminski@enron.com"
NOW = datetime(2026, 9, 28, 9, 30, tzinfo=UTC)          # 15:00 in Kolkata: not quiet hours
TZ = "Asia/Kolkata"


def mail(ref, sent, sender, body, subject="Model review"):
    return Message(ref, "inbox", sent, sender, (OWNER,), (), subject, body)


def belief(conn, item, kind, statement, due=None, actor="vince kaminski", trust="engram", status="open"):
    return conn.execute(
        "INSERT INTO beliefs (kind, actor, statement, due_at, valid, item_id, quote, confidence, trust, status) "
        "VALUES (%s, %s, %s, %s, tstzrange(now(), NULL), %s, %s, 0.9, %s, %s) RETURNING id",
        (kind, actor, statement, due, item, statement, trust, status)).fetchone()["id"]


@pytest.fixture
def brain(db_url):
    with connect(db_url) as conn:
        conn.execute("TRUNCATE herald_cards, belief_links, labels, memory_scans, beliefs, item_refs, chunks, items "
                     "RESTART IDENTITY CASCADE")
        ingest_messages(conn, [
            mail("h/1", NOW - timedelta(days=30), "stinson.gibner@enron.com", "I will send the model on Friday."),
            mail("h/2", NOW - timedelta(days=29), "stinson.gibner@enron.com", "Attached is the model, as promised."),
            mail("h/3", NOW - timedelta(hours=3), "stinson.gibner@enron.com", "Can we meet Monday at 3 pm?",
                 "Meeting"),
            mail("h/4", NOW - timedelta(days=90), "stinson.gibner@enron.com", "Let us meet in June.", "Old"),
        ], {OWNER}, "enron", "email")
        ids = {r["ref"]: r["item_id"] for r in conn.execute("SELECT ref, item_id FROM item_refs")}
        b = {"due": belief(conn, ids["h/1"], "commitment", "Vince sends Stinson the deck", NOW + timedelta(minutes=40)),
             "later": belief(conn, ids["h/1"], "commitment", "Vince reviews the paper", NOW + timedelta(days=3)),
             "promise": belief(conn, ids["h/1"], "commitment", "Stinson sends the model", actor="stinson gibner"),
             "fresh": belief(conn, ids["h/3"], "meeting", "Stinson meets Vince on Monday at 3 pm"),
             "old": belief(conn, ids["h/4"], "meeting", "Stinson meets Vince in June")}
        conn.execute("INSERT INTO memory_scans (item_id, kinds) VALUES (%s, '{meeting}'), (%s, '{meeting}')",
                     (ids["h/3"], ids["h/4"]))
        link = conn.execute("INSERT INTO belief_links (kind, belief_id, item_id, p, settled) VALUES "
                            "('fulfils', %s, %s, 0.6, false) RETURNING id", (b["promise"], ids["h/2"])).fetchone()["id"]
        conn.commit()
    return db_url, ids, b, link


def test_each_role_posts_once_and_urgent_cards_buzz(brain):
    url, ids, b, link = brain
    with connect(url) as conn:
        posted = {c["subject"]: c for c in herald.sweep(conn, NOW, TZ, {"vince kaminski"})}
        assert set(posted) == {f"belief:{b['due']}:due", f"link:{link}", f"item:{ids['h/3']}"}   # not the old
        due = posted[f"belief:{b['due']}:due"]
        assert (due["title"], due["route"]) == ("Due in 40 min", "now")
        assert posted[f"link:{link}"]["route"] == "digest"                  # a check is not urgent
        assert posted[f"item:{ids['h/3']}"]["title"] == "New from stinson.gibner"
        assert posted[f"item:{ids['h/3']}"]["route"] == "now"               # a fresh meeting request
        assert herald.sweep(conn, NOW, TZ, {"vince kaminski"}) == []        # posted once
        shown = herald.cards(conn, NOW)
        assert [c["route"] for c in shown] == ["now", "now", "digest"]      # buzz-worthy first


def test_quiet_hours_and_the_buzz_budget_hold_urgent_cards_back(brain):
    url, *_ = brain
    with connect(url) as conn:
        night = datetime(2026, 9, 28, 18, 0, tzinfo=UTC)                    # 23:30 in Kolkata
        assert herald.route(conn, {"urgent": "a promise is due"}, night, TZ) == \
            ("digest", "a promise is due, but quiet hours")
        for i in range(herald.BUDGET):
            conn.execute("INSERT INTO herald_cards (role, kind, subject, title, actions, route, why, created_at) "
                         "VALUES ('memory', 'due', %s, 't', '[]', 'now', 'x', %s)", (f"x:{i}", NOW))
        assert herald.route(conn, {"urgent": "a promise is due"}, NOW, TZ)[0] == "digest"


def test_the_owners_taps_go_back_to_the_role_and_into_the_ledger(brain):
    url, _, b, link = brain
    with connect(url) as conn:
        herald.sweep(conn, NOW, TZ, {"vince kaminski"})
        by_subject = {c["subject"]: c for c in conn.execute("SELECT id, subject FROM herald_cards")}
        due, check = by_subject[f"belief:{b['due']}:due"]["id"], by_subject[f"link:{link}"]["id"]
        herald.cards(conn, NOW, deliver=True)

        assert herald.decide(conn, due, "snooze", "watch:galaxy", NOW)["ok"]
        assert due not in [c["id"] for c in herald.cards(conn, NOW)]                          # hidden for an hour
        assert due in [c["id"] for c in herald.cards(conn, NOW + timedelta(minutes=61))]      # and back
        herald.decide(conn, due, "done", "watch:galaxy", NOW + timedelta(minutes=61))
        assert conn.execute("SELECT status FROM beliefs WHERE id = %s", (b["due"],)).fetchone()["status"] == "done"
        with pytest.raises(LookupError):
            herald.decide(conn, due, "done", "watch:galaxy", NOW)                            # once
        with pytest.raises(ValueError):
            herald.decide(conn, check, "done", "watch:galaxy", NOW)                          # not an answer here

        herald.decide(conn, check, "yes", "watch:galaxy", NOW)                               # it was fulfilled
        assert conn.execute("SELECT verdict FROM belief_links WHERE id = %s", (link,)).fetchone()["verdict"] == \
            "confirmed"
        assert conn.execute("SELECT status FROM beliefs WHERE id = %s", (b["promise"],)).fetchone()["status"] == "done"
        label = conn.execute("SELECT value, source FROM labels WHERE question = 'fulfilled'").fetchone()
        assert label == {"value": "yes", "source": "human"}
        assert conn.execute("SELECT 1 FROM label_examples WHERE question = 'fulfilled'").fetchone()  # trainable

        taps = conn.execute("SELECT question, model, value FROM judgements WHERE tier = 'H' ORDER BY id").fetchall()
        assert [(t["question"], t["value"]) for t in taps] == [("herald:due", "done"), ("herald:fulfils", "yes")]
        assert {t["model"] for t in taps} == {"owner:watch:galaxy"} and verify_ledger(conn) is None


def test_rejecting_a_fulfilment_the_judge_settled_reopens_the_commitment(brain):
    url, ids, b, _ = brain
    with connect(url) as conn:
        conn.execute("UPDATE beliefs SET status = 'done' WHERE id = %s", (b["later"],))      # the judge closed it
        link = conn.execute("INSERT INTO belief_links (kind, belief_id, item_id, p, settled) VALUES "
                            "('fulfils', %s, %s, 0.97, true) RETURNING id", (b["later"], ids["h/2"])).fetchone()["id"]
        conn.commit()
        herald.sweep(conn, NOW, TZ, set())
        card = conn.execute("SELECT id, title FROM herald_cards WHERE subject = %s", (f"link:{link}",)).fetchone()
        assert card["title"] == "Done? (the judge closed it)"
        herald.decide(conn, card["id"], "no", "watch:galaxy", NOW)
        assert conn.execute("SELECT status FROM beliefs WHERE id = %s", (b["later"],)).fetchone()["status"] == "open"
