"""Memory building with scripted models: gating, the quote check, time resolution and supersession."""
import math
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from engram.db import connect
from engram.judge import Judge
from engram.memory import build, quote_in, resolve_when
from engram.sources.enron import Message
from engram.store import ingest_messages

OWNER = "vince.kaminski@enron.com"


class ByPrompt:
    """P(yes) chosen by which phrase appears in the prompt; anything else is a confident no."""

    model = "scripted"

    def __init__(self, yes_when: tuple[str, ...]):
        self.yes_when = yes_when

    def score(self, system, user, keys):
        p = 0.98 if any(s in user for s in self.yes_when) else 0.02
        return {"yes": math.log(p), "no": math.log(1 - p)}


class FakeExtractor:
    def __init__(self, items):
        self.items, self.calls = items, 0

    def generate_json(self, model, system, user, schema, max_tokens=600):
        self.calls += 1
        return {"items": self.items(user)}


def test_quote_check_is_verbatim_but_forgiving_of_case_and_spacing():
    text = "Hi Vince,\n\nI will send the  revised model by Friday.\nThanks"
    assert quote_in("I will send the revised model by Friday.", text)
    assert not quote_in("I will send the final model by Monday", text)
    assert not quote_in("ok", text)                       # too short to mean anything


def test_time_words_are_resolved_against_the_email_date():
    wednesday = datetime(2000, 10, 4, 15, 0, tzinfo=UTC)
    friday = resolve_when("Friday", wednesday, "America/Chicago")
    assert friday is not None and friday.date() == datetime(2000, 10, 6).date()
    assert resolve_when("", wednesday, "America/Chicago") is None
    evening = datetime(2001, 5, 15, 2, 39, tzinfo=UTC)                      # 21:39 on Monday 14 May in Houston
    tomorrow = resolve_when("tomorrow", evening, "America/Chicago")
    assert tomorrow is not None and tomorrow.astimezone(ZoneInfo("America/Chicago")).day == 15


@pytest.mark.db
def test_build_gates_extracts_checks_quotes_and_supersedes(db_url):
    def mail(ref, day, body):
        return Message(ref, "inbox", datetime(2000, 10, day, 15, tzinfo=UTC), "stinson.gibner@enron.com", (OWNER,),
                       (), "Model review", body)

    with connect(db_url) as conn:
        ingest_messages(conn, [mail("v/inbox/20.", 2, "Vince, I will send you the revised model by Friday. Stinson"),
                               mail("v/inbox/21.", 3, "Vince, sorry, I will send you the revised model on Monday."),
                               mail("v/inbox/22.", 3, "Thanks for lunch today, it was great to catch up.")], {OWNER})

    def items(user):
        if "by Friday" in user:
            return [{"kind": "commitment", "actor": "Stinson", "other": "Vince", "statement": "Stinson will send the "
                     "revised model", "when": "Friday", "quote": "I will send you the revised model by Friday"},
                    {"kind": "commitment", "actor": "Stinson", "other": "Vince", "statement": "Invented",
                     "when": "", "quote": "I promise a pay rise"}]                         # not in the email
        return [{"kind": "commitment", "actor": "Stinson", "other": "Vince", "statement": "Stinson will send the "
                 "revised model", "when": "Monday", "quote": "I will send you the revised model on Monday"}]

    extractor = FakeExtractor(items)
    judge_scorer = ByPrompt(("I will send", "Existing:"))                  # gates on promises; SAME says yes
    with connect(db_url) as conn, Judge(db_url, judge_scorer) as judge:
        stats = build(conn, judge, extractor, "m", "Vince Kaminski", "America/Chicago")
        again = build(conn, judge, extractor, "m", "Vince Kaminski", "America/Chicago")
        current = conn.execute("SELECT statement, when_text, supersedes FROM current_beliefs").fetchall()
        total = conn.execute("SELECT count(*) AS n FROM beliefs").fetchone()["n"]
    assert (stats.scanned, stats.extraction_calls, stats.unquoted) == (3, 2, 1)   # the lunch note stops at the gate
    assert stats.passed == 2 and stats.superseded == 1
    assert again.scanned == 0                                                       # resumable: nothing new
    assert total == 2 and len(current) == 1 and current[0]["when_text"] == "Monday" and current[0]["supersedes"]


@pytest.mark.db
def test_bad_output_never_blocks_and_older_news_never_replaces_newer(db_url):
    def mail(ref, day, body):
        return Message(ref, "inbox", datetime(2000, 11, day, 15, tzinfo=UTC), "shirley.crenshaw@enron.com",
                       (OWNER,), (), "Offsite", body)

    with connect(db_url) as conn:
        ingest_messages(conn, [mail("v/inbox/30.", 9, "Vince, I will book the offsite room for the 20th."),
                               mail("v/inbox/31.", 10, "Vince, I will book the offsite room for the 21st, not 20th."),
                               mail("v/inbox/32.", 11, "Vince, I will call the caterer about the offsite.")], {OWNER})

    class Extractor:
        def generate_json(self, model, system, user, schema, max_tokens=600):
            if "caterer" in user:
                raise ValueError("Unterminated string")                     # output cut off at the token limit
            day = "21st" if "21st" in user else "20th"
            return {"items": [{"kind": "commitment", "actor": "Shirley", "other": "Vince", "statement": "Shirley "
                               f"will book the offsite room for the {day}", "when": f"the {day}",
                               "quote": f"I will book the offsite room for the {day}"}, {"kind": "commitment"}]}

    judge_scorer = ByPrompt(("I will", "Existing:"))
    with connect(db_url) as conn, Judge(db_url, judge_scorer) as judge:
        newest = build(conn, judge, Extractor(), "m", "Vince", "America/Chicago", since=datetime(2000, 11, 10))
        backfill = build(conn, judge, Extractor(), "m", "Vince", "America/Chicago")    # the older email, later
        rows = conn.execute("SELECT when_text, upper_inf(recorded) AS current, upper(valid) AS until "
                            "FROM beliefs WHERE actor = 'shirley' ORDER BY id").fetchall()
    assert newest.malformed == 2 and newest.scanned == 2 and backfill.scanned == 1    # the bad item is not retried
    assert [(r["when_text"], r["current"]) for r in rows] == [("the 21st", True), ("the 20th", False)]
    assert rows[1]["until"] == datetime(2000, 11, 10, 15, tzinfo=UTC)                  # valid until the newer news


class Rules:
    """P(yes) = 0.98 when every phrase of some rule is in the prompt; otherwise a confident no."""

    model = "scripted"

    def __init__(self, *rules: tuple[str, ...]):
        self.rules = rules

    def score(self, system, user, keys):
        p = 0.98 if any(all(s in user for s in rule) for rule in self.rules) else 0.02
        return {"yes": math.log(p), "no": math.log(1 - p)}


@pytest.mark.db
def test_a_later_message_in_the_thread_fulfils_an_open_commitment(db_url):
    def mail(ref, day, sender, to, body):
        return Message(ref, "inbox", datetime(2000, 12, day, 15, tzinfo=UTC), sender, (to,), (), "Revised model",
                       body)

    with connect(db_url) as conn:
        ingest_messages(conn, [mail("v/inbox/40.", 4, "stinson.gibner@enron.com", OWNER,
                                    "Vince, I will send you the revised model by Friday."),
                               mail("v/inbox/41.", 5, "stinson.gibner@enron.com", OWNER,
                                    "Vince, still working on the revised model, nearly there."),
                               mail("v/inbox/42.", 8, "stinson.gibner@enron.com", OWNER,
                                    "Vince, attached is the revised model as promised.")], {OWNER})

    class Extractor:
        def generate_json(self, model, system, user, schema, max_tokens=600):
            if "I will send" not in user:
                return {"items": []}
            return {"items": [{"kind": "commitment", "actor": "Stinson", "other": "Vince", "statement": "Stinson "
                               "will send the revised model", "when": "Friday",
                               "quote": "I will send you the revised model by Friday"}]}

    scorer = Rules(("should remember", "I will send"), ("carried out", "attached is the revised model"))
    with connect(db_url) as conn, Judge(db_url, scorer) as judge:
        build(conn, judge, Extractor(), "m", "Vince Kaminski", "America/Chicago")
        belief = conn.execute("SELECT id, status FROM current_beliefs WHERE subject = 'Revised model'").fetchone()
        links = conn.execute("SELECT l.kind, l.belief_id, l.settled, i.body FROM belief_links l "
                             "JOIN items i ON i.id = l.item_id WHERE l.kind = 'fulfils' AND l.belief_id = %s",
                             (belief["id"],)).fetchall()
    assert belief["status"] == "done" and len(links) == 1                # progress reports do not count
    assert links[0]["settled"] and "attached" in links[0]["body"]


@pytest.mark.db
def test_a_new_belief_that_goes_against_a_decision_is_linked_not_acted_on(db_url):
    def mail(ref, day, subject, body):
        return Message(ref, "inbox", datetime(2001, 1, day, 15, tzinfo=UTC), "stinson.gibner@enron.com", (OWNER,),
                       (), subject, body)

    with connect(db_url) as conn:
        ingest_messages(conn, [mail("v/inbox/50.", 8, "Vendor", "Vince, we decided to use Pinnacle as the vendor."),
                               mail("v/inbox/51.", 9, "Contract", "Vince, I will sign the contract with Delta."),
                               mail("v/inbox/52.", 10, "Lunch", "Vince, I will bring the slides to lunch.")], {OWNER})

    class Extractor:
        def generate_json(self, model, system, user, schema, max_tokens=600):
            for quote, kind, statement in (("we decided to use Pinnacle", "decision", "Use Pinnacle as the vendor"),
                                           ("I will sign the contract with Delta", "commitment", "Sign with Delta"),
                                           ("I will bring the slides", "commitment", "Bring the slides")):
                if quote in user:
                    return {"items": [{"kind": kind, "actor": "Stinson", "other": "Vince", "statement": statement,
                                       "when": "", "quote": quote}]}
            return {"items": []}

    scorer = Rules(("should remember",), ("not both hold", "Pinnacle", "Delta"))
    with connect(db_url) as conn, Judge(db_url, scorer) as judge:
        stats = build(conn, judge, Extractor(), "m", "Vince Kaminski", "America/Chicago")
        links = conn.execute("SELECT l.kind, o.statement AS old, n.statement AS new, l.verdict FROM belief_links l "
                             "JOIN beliefs o ON o.id = l.belief_id JOIN beliefs n ON n.id = l.new_belief "
                             "WHERE l.kind = 'contradicts'").fetchall()
        current = conn.execute("SELECT count(*) AS n FROM current_beliefs "
                               "WHERE subject IN ('Vendor', 'Contract', 'Lunch')").fetchone()["n"]
    assert stats.contradictions == 1 and current == 3                     # both kept: the owner decides
    assert [(r["kind"], r["old"], r["new"], r["verdict"]) for r in links] == [
        ("contradicts", "Use Pinnacle as the vendor", "Sign with Delta", "pending")]


@pytest.mark.db
def test_a_note_the_owner_says_to_remember_skips_the_gate_and_the_running_build(db_url):
    """ "Remember …" on the watch: the gate would say no, but the owner decided. The belief is the owner's, the
    decision becomes a human label, and a long scan build holding the brain's lock does not hold the note up."""
    note = Message("upload/n1", "upload", datetime(2026, 9, 28, 8, tzinfo=UTC), "owner", (), (), "Voice note",
                   "Tomorrow 4 pm I have a meeting with the design team.")
    extractor = FakeExtractor(lambda user: [{"kind": "meeting", "actor": "owner", "other": "design team",
                                             "statement": "owner meets the design team", "when": "tomorrow 4 pm",
                                             "quote": "Tomorrow 4 pm I have a meeting"}])
    with connect(db_url) as conn, connect(db_url) as other, Judge(db_url, ByPrompt(())) as judge:
        ingest_messages(conn, [note], {"owner"}, "upload", "note")
        conn.commit()
        item = conn.execute("SELECT item_id FROM item_refs WHERE ref = 'upload/n1'").fetchone()["item_id"]
        assert other.execute("SELECT pg_try_advisory_lock(%s) AS ok", (0x656E6D65,)).fetchone()["ok"]  # a scan build
        with pytest.raises(RuntimeError):
            build(conn, judge, extractor, "m", OWNER, "America/Chicago")          # a second scan build waits its turn
        stats = build(conn, judge, extractor, "m", OWNER, "America/Chicago", ids=[item], owner_says=[item])
        assert stats.beliefs == 1 and extractor.calls == 1
        b = conn.execute("SELECT kind, trust FROM current_beliefs WHERE item_id = %s", (item,)).fetchone()
        assert b == {"kind": "meeting", "trust": "owner"}
        assert conn.execute("SELECT value, source FROM labels WHERE question = 'remember' AND subject = %s",
                            (f"item:{item}",)).fetchone() == {"value": "yes", "source": "human"}
        assert not conn.execute("SELECT 1 FROM judgements WHERE question = 'remember' AND subject = %s",
                                (f"item:{item}",)).fetchone()                   # the judge was not asked
        assert build(conn, judge, extractor, "m", OWNER, "America/Chicago", ids=[item]).scanned == 0   # once only
