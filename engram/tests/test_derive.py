"""Adapter v2's derived labels: what each derivation calls yes and no, the gold set kept out, and the team's check."""
import random
from datetime import UTC, datetime

import pytest

from engram import derive, people
from engram.db import connect
from engram.sources.enron import Message
from engram.store import ingest_messages

OWNER = "vince.kaminski@enron.com"
STINSON = "stinson.gibner@enron.com"


def mail(ref, day, sender, to, subject, body):
    return Message(ref, "inbox", datetime(2000, 10, day, 15, tzinfo=UTC), sender, (to,), (), subject, body)


def belief(conn, item, kind, statement, when="", supersedes=None, actor="stinson gibner", other="vince kaminski"):
    return conn.execute(
        "INSERT INTO beliefs (kind, actor, other, statement, when_text, valid, item_id, quote, confidence, supersedes) "
        "VALUES (%s, %s, %s, %s, %s, tstzrange(now(), NULL), %s, %s, 0.9, %s) RETURNING id",
        (kind, actor, other, statement, when, item, statement, supersedes)).fetchone()["id"]


@pytest.fixture(scope="module")
def brain(db_url):
    with connect(db_url) as conn:
        ingest_messages(conn, [
            mail("d/1.", 2, STINSON, OWNER, "Revised model", "Vince, I will send you the revised model by Friday."),
            mail("d/2.", 5, STINSON, OWNER, "Revised model", "Vince, attached is the revised model."),
            mail("d/3.", 6, OWNER, STINSON, "Revised model", "Stinson, any news on the model? Vince"),
            mail("d/4.", 3, STINSON, OWNER, "Review", "Vince, can we meet Tuesday at 3pm for the review?"),
            mail("d/5.", 4, STINSON, OWNER, "Review", "Vince, can we meet Wednesday at 4pm instead?"),
            mail("d/6.", 7, STINSON, OWNER, "Vendor", "Vince, we decided to use Pinnacle as the vendor."),
            mail("d/7.", 8, "news@energy.com", OWNER, "Weekly", "This week in power markets. Click here to "
                 "unsubscribe from this newsletter."),
        ], {OWNER})
        ids = {r["ref"]: r["item_id"] for r in conn.execute("SELECT ref, item_id FROM item_refs")}
        promise = belief(conn, ids["d/1."], "commitment", "Stinson will send the revised model", "Friday")
        tuesday = belief(conn, ids["d/4."], "meeting", "Review meeting", "Tuesday at 3pm")
        wednesday = belief(conn, ids["d/5."], "meeting", "Review meeting", "Wednesday at 4pm", supersedes=tuesday)
        conn.execute("UPDATE beliefs SET recorded = tstzrange(lower(recorded), now()) WHERE id = %s", (tuesday,))
        vendor = belief(conn, ids["d/6."], "decision", "Use Pinnacle as the vendor")
        for ref, kinds in (("d/1.", ["commitment"]), ("d/2.", []), ("d/3.", []), ("d/4.", ["meeting"]),
                           ("d/5.", ["meeting"]), ("d/6.", ["decision"])):
            conn.execute("INSERT INTO memory_scans (item_id, kinds) VALUES (%s, %s)", (ids[ref], kinds))
        conn.commit()
        people.build(conn)
    return {"ids": ids, "promise": promise, "tuesday": tuesday, "wednesday": wednesday, "vendor": vendor}


def labelled(conn, name):
    return {e.subject: e.label for e in derive.examples(conn, name)}


@pytest.mark.db
def test_each_derivation_reads_the_brains_own_structure(db_url, brain):
    ids = brain["ids"]
    with connect(db_url) as conn:
        added = derive.queue(conn, 10, random.Random(0), gold={ids["d/1."]})
        fulfilled, contradicts = labelled(conn, "fulfilled"), labelled(conn, "contradicts")
        meeting, remember = labelled(conn, "meeting_request"), labelled(conn, "remember")
        again = derive.queue(conn, 10, random.Random(0), gold={ids["d/1."]})
    p = brain["promise"]
    assert fulfilled == {f"belief:{p}|item:{ids['d/2.']}": "yes",          # the actor, and "attached"
                         f"belief:{p}|item:{ids['d/3.']}": "no"}           # the owner asking is not delivery
    assert contradicts[f"belief:{brain['tuesday']}|belief:{brain['wednesday']}"] == "yes"   # the time moved
    assert contradicts[f"belief:{p}|belief:{brain['vendor']}"] == "no"     # same person, unrelated
    assert {s for s, v in meeting.items() if v == "yes"} == {f"item:{ids['d/4.']}", f"item:{ids['d/5.']}"}
    assert meeting[f"item:{ids['d/7.']}"] == "no"                          # bulk mail
    assert f"item:{ids['d/1.']}" not in remember | meeting                 # the gold set never reaches training
    assert remember[f"item:{ids['d/7.']}"] == "no" and remember[f"item:{ids['d/6.']}"] == "yes"
    derived = ("remember", "meeting_request", "fulfilled", "contradicts")
    assert all(added[k] > 0 for k in derived) and not any(again[k] for k in derived)   # idempotent


@pytest.mark.db
def test_the_teams_check_beats_the_derived_label_and_is_measured(db_url, brain):
    ids, p = brain["ids"], brain["promise"]
    subject = f"belief:{p}|item:{ids['d/2.']}"
    with connect(db_url) as conn:
        derive.check(conn, "fulfilled", subject, "no")                     # the team disagrees
        derive.check(conn, "fulfilled", f"belief:{p}|item:{ids['d/3.']}", "skip")
        mine = derive.examples(conn, "fulfilled", human_only=True)
        report = derive.agreement(conn)["fulfilled"]
        left = derive.next_to_check(conn, "fulfilled")
        with pytest.raises(LookupError):
            derive.check(conn, "fulfilled", "belief:0|item:0", "yes")
        with pytest.raises(ValueError):
            derive.check(conn, "fulfilled", subject, "maybe")
    assert [(e.subject, e.label, e.source) for e in mine] == [(subject, "no", "human")]   # skips stay out
    assert report == {"queued": 2, "checked": 2, "skipped": 1, "derived_right": 0.0}
    assert left is None


@pytest.mark.db
def test_todo_has_no_derived_label_and_trains_on_the_teams_check_alone(db_url, brain):
    ids = brain["ids"]
    with connect(db_url) as conn:
        mine = belief(conn, ids["d/3."], "commitment", "Vince will review the model", actor="vince kaminski",
                      other="stinson gibner")
        conn.commit()
        derive.queue(conn, 10, random.Random(0))
        before = derive.examples(conn, "todo")
        waiting = derive.next_to_check(conn, "todo")
        derive.check(conn, "todo", f"belief:{mine}", "yes")
        after = derive.examples(conn, "todo")
        report = derive.agreement(conn)["todo"]
    assert before == [] and waiting["subject"] == f"belief:{mine}" and "review the model" in waiting["state"]
    assert [(e.label, e.source) for e in after] == [("yes", "human")]
    assert report["derived_right"] is None                                  # nothing derived to compare with


@pytest.mark.db
def test_an_owner_verdict_from_the_watch_becomes_a_training_example(db_url, brain):
    ids, p = brain["ids"], brain["promise"]
    with connect(db_url) as conn:
        subject = derive.owner_verdict(conn, "contradicts", brain["vendor"], "yes", new_belief=p)
        conn.commit()
        got = {e.subject: (e.label, e.source, e.state) for e in derive.examples(conn, "contradicts", human_only=True)}
        with pytest.raises(ValueError):
            derive.owner_verdict(conn, "fulfilled", p, "yes")                  # fulfilled needs the item
        with pytest.raises(LookupError):
            derive.owner_verdict(conn, "fulfilled", p, "yes", item=10**9)
    assert subject == f"belief:{brain['vendor']}|belief:{p}"
    label, source, state = got[subject]
    assert (label, source) == ("yes", "human") and "Pinnacle" in state and "revised model" in state
    assert ids                                                                  # the shared fixture is in use
