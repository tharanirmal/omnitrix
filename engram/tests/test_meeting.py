"""Feature 2, the smart meeting reply: time words, the calendar, the Fact Checker, and the pipeline to the gate."""
import math
from datetime import datetime, timedelta

import pytest

from engram.act import Gate, Tool
from engram.judge import Judge
from engram.meeting import Email, Event, carry_out, check, free_slots, problem, propose, resolve, template, when

NOW = datetime(2023, 11, 30, 10, 0)             # WorkBench's Thursday
EVENTS = [Event(datetime(2023, 11, 30, 17, 0), 60, "board prep"), Event(datetime(2023, 12, 1, 9, 0), 120, "offsite")]


def mail(body, subject="Quick sync"):
    return Email("00000900", "raj.mehta@atlas.com", subject, NOW, body)


class Scripted:
    """The judge says yes to `meeting_request` when the email mentions meeting."""

    model = "scripted"

    def score(self, system, user, keys):
        p = 0.97 if "meet" in user.split("---")[0].lower() else 0.03
        return {"yes": math.log(p), "no": math.log(1 - p)}


class FakeLLM:
    def __init__(self, when_words, drafts):
        self.when_words, self.drafts, self.prompts = when_words, list(drafts), []

    def generate_json(self, model, system, user, schema, max_tokens=600):
        return {"topic": "Q4 pricing", "when": self.when_words, "minutes": 30}

    def chat(self, model, messages, tools=None, fmt=None, think=False, max_tokens=1024):
        self.prompts.append(messages[-1]["content"])
        return {"content": self.drafts.pop(0)}


def test_time_words_resolve_from_the_email_date_and_need_a_clock_time():
    assert resolve("today at 5 PM", NOW) == datetime(2023, 11, 30, 17, 0)
    assert resolve("tomorrow at 11am", NOW) == datetime(2023, 12, 1, 11, 0)
    assert resolve("Friday", NOW) is None and resolve("", NOW) is None
    assert resolve("tomorrow at 3", NOW) is None                         # 3 am or 3 pm? not a time to accept


def test_the_calendar_says_why_a_time_does_not_work():
    assert problem(datetime(2023, 11, 30, 15, 0), 30, EVENTS, NOW) == ""
    assert problem(datetime(2023, 11, 30, 17, 30), 30, EVENTS, NOW).startswith("busy at")
    assert "protected" in problem(datetime(2023, 11, 30, 13, 0), 30, EVENTS, NOW)
    assert "outside working hours" in problem(datetime(2023, 11, 30, 17, 45), 30, [], NOW)
    assert "passed" in problem(datetime(2023, 11, 30, 9, 0), 30, EVENTS, NOW)
    assert "weekend" in problem(datetime(2023, 12, 2, 10, 0), 30, EVENTS, NOW)


def test_offered_slots_are_free_spread_over_working_days_and_skip_lunch_and_weekends():
    slots = free_slots(EVENTS, datetime(2023, 11, 30, 12, 50), 30, 3)
    assert slots == [datetime(2023, 11, 30, 14, 0), datetime(2023, 12, 1, 11, 0), datetime(2023, 12, 4, 9, 0)]


def test_the_fact_checker_wants_exactly_the_offered_times_and_the_right_name():
    t = when(datetime(2023, 11, 30, 17, 0))
    assert t == "Thursday 30 November at 5:00 PM"
    assert check(f"Hi Raj, {t} works. Sam", [t], "Raj") == []
    assert check(f"Hi Raj, {t} or 6 PM works. Sam", [t], "Raj") == ["mentions 6 PM, which was not offered"]
    assert check("Hi Priya, see you then. Sam", [t], "Raj") == [f"missing '{t}'", "does not greet Raj"]
    assert check(f"Hi Raj, 5 PM today doesn't work; {t}? Sam", [t], "Raj", "Can we meet today at 5 PM?") == []
    assert check(f"Hi Raj, I have board prep then; {t}? Sam", [t], "Raj", private=["board prep"]) == [
        "reveals the owner's calendar (board prep)"]
    assert check(f"Hi Raj, let's sync on the Monday planning at {t}. Sam", [t], "Raj", "Monday planning",
                 ["sync", "call"]) == []                                  # their topic; everyday words
    assert check(f"Hi Raj,\u00a0{t.replace(' ', chr(160), 1)} works. Sam", [t], "Raj") == []


@pytest.mark.db
def test_a_free_time_is_accepted_and_the_reply_and_event_wait_for_the_gate(db_url):
    t = "Thursday 30 November at 3:00 PM"
    llm = FakeLLM("today at 3 PM", [f"Hi Raj,\n\n{t} works for me.\n\nSam"])
    with Judge(db_url, Scripted()) as judge:
        pr = propose(mail("Hi Sam, can we meet today at 3 PM about Q4 pricing?"), judge, llm, "m", EVENTS, NOW, 7)
    assert pr.decision == "accept" and pr.slots == [datetime(2023, 11, 30, 15, 0)] and pr.drafted_by == "model"
    assert [r.role for r in pr.steps] == ["Librarian", "Researcher", "Planner", "Writer", "Fact Checker"]
    assert pr.headline == f"Raj: {t}, you're free" and "frequent contact" in pr.contact
    (reply, a), (event, b) = pr.actions()
    assert (reply, a["email_id"], event) == ("email.reply_email", "00000900", "calendar.create_event")
    assert b == {"event_name": "Q4 pricing", "participant_email": "raj.mehta@atlas.com",
                 "event_start": "2023-11-30 15:00:00", "duration": "30"}

    ran = []
    tools = {n: Tool(n, "external", lambda n=n, **kw: ran.append(n) or "ok") for n in (reply, event)}
    asked = []
    carry_out(pr, tools, Gate(None, lambda req, tool, args, v: asked.append(req) or True), "meeting:test")
    assert ran == [reply, event] and "add it to my calendar at " + t in asked[0]
    ran.clear()
    denied = carry_out(pr, tools, Gate(None, lambda *a: False), "meeting:test")
    assert ran == [] and [c.reason for _, c, _ in denied] == ["awaiting approval"] * 2       # nothing leaves


@pytest.mark.db
def test_a_clash_offers_other_times_redrafts_once_then_falls_back_to_the_template(db_url):
    bad = "Hi Raj, how about 6 PM? Sam"                                   # a time that was never offered
    with Judge(db_url, Scripted()) as judge:
        pr = propose(mail("Can we meet today at 5pm?"), judge, FakeLLM("today at 5pm", [bad, bad]), "m", EVENTS,
                     NOW)
    assert pr.decision == "propose" and pr.why.startswith("busy at") and len(pr.slots) == 3
    assert pr.drafted_by == "template" and check(pr.reply, [when(s) for s in pr.slots], "Raj") == []
    assert [a for a, _ in pr.actions()] == ["email.reply_email"]          # no event until a time is agreed
    assert template(pr, "Sam", [when(s) for s in pr.slots]) == pr.reply


@pytest.mark.db
def test_a_fully_booked_calendar_asks_the_sender_to_suggest_a_time(db_url):
    busy = [Event(datetime(2023, 11, 30, 9) + timedelta(days=d), 9 * 60) for d in range(40)]   # 9-18 daily
    with Judge(db_url, Scripted()) as judge:
        pr = propose(mail("Can we meet this week?"), judge, FakeLLM("", []), "m", busy, NOW)
    assert pr.slots == [] and pr.drafted_by == "template" and "fully booked" in pr.reply
    assert "no free time" in pr.why


@pytest.mark.db
def test_an_email_that_is_not_a_meeting_request_stops_at_the_librarian(db_url):
    with Judge(db_url, Scripted()) as judge:
        pr = propose(mail("Attached is the revised budget.", "Budget"), judge, FakeLLM("", []), "m", EVENTS, NOW)
    assert pr.decision == "not_meeting" and pr.actions() == [] and [s.role for s in pr.steps] == ["Librarian"]


@pytest.mark.db
def test_the_server_runs_a_meeting_reply_through_the_owners_approval(db_url, tmp_path, monkeypatch):
    """Brain.meeting end to end with the models and the sandbox stubbed: the pipeline's steps show, the reply
    waits for the owner with a card for the watch, the watch approves, the reply is sent and the event created,
    and both decisions are in the ledger."""
    import time

    from engram import meeting as mt
    from engram import serve as srv
    from engram.config import Settings
    from engram.db import connect
    from engram.judge import verify_ledger
    from engram.meeting import Proposal, Step

    email = mail("Can we meet today at 3 PM?")
    pr = Proposal(email, "accept", 0.97, "Q4 pricing", "today at 3 PM", datetime(2023, 11, 30, 15), 30, "",
                  [datetime(2023, 11, 30, 15)], "7 emails", "Hi Raj, Thursday 30 November at 3:00 PM works. Sam",
                  "model", [Step("Librarian", "meeting request", 5), Step("Planner", "free", 1)])
    ran = []
    tools = [Tool(n, "external", lambda n=n, **a: ran.append(n) or "ok")
             for n in ("email.reply_email", "calendar.create_event")]
    monkeypatch.setattr(mt, "wb_email", lambda i: email)
    monkeypatch.setattr(mt, "wb_calendar", lambda: [])
    monkeypatch.setattr(mt, "wb_contacts", lambda s: 7)
    monkeypatch.setattr(mt, "propose", lambda *a, **k: pr)
    monkeypatch.setattr(srv.wb, "tools", lambda domains: tools)
    monkeypatch.setattr(srv, "Gate", lambda judge, approve: Gate(None, approve))      # no model for the intent
    brain = srv.Brain(Settings(database_url=db_url, data_dir=tmp_path), workbench=True)
    monkeypatch.setattr(brain, "judge", lambda: None)
    try:
        run_id = brain.meeting({"email_id": email.email_id})["id"]
        for tool in ("email.reply_email", "calendar.create_event"):     # the reply, then the calendar event
            for _ in range(200):
                pending = brain.pending()["pending"]
                if pending and pending[0]["tool"] == tool:
                    break
                time.sleep(0.05)
            assert pending[0]["card"]["headline"] == "Raj: Thursday 30 November at 3:00 PM, you're free"
            assert "3:00 PM works" in pending[0]["card"]["reply"] and pending[0]["on_watch"]
            brain.decide(run_id, True, "watch:galaxy")
        for _ in range(100):
            if brain.runs[run_id].status == "done":
                break
            time.sleep(0.05)
        state = brain.run_state(run_id)
        assert state["status"] == "done" and ran == ["email.reply_email", "calendar.create_event"]
        assert [(e.start, e.minutes) for e in brain.booked] == [(datetime(2023, 11, 30, 15), 30)]  # next run sees it
        assert [s["tool"] for s in state["steps"]] == ["Librarian", "Planner", "Operator", "Operator"]
        with connect(db_url) as conn:
            rows = conn.execute("SELECT model, value FROM judgements WHERE subject = %s ORDER BY id",
                                (f"act:{run_id}",)).fetchall()
            assert rows == [{"model": "owner:watch:galaxy", "value": "yes"}] * 2 and verify_ledger(conn) is None
        with pytest.raises(ValueError):
            brain.meeting({})
    finally:
        brain.llm.close()
