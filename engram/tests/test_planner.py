"""Planner: the solver's placement, and a day planned, missed and re-planned."""
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from engram import people
from engram.db import connect
from engram.planner import Task, owner_names, plan_day, solve
from engram.sources.enron import Message
from engram.store import ingest_messages

TZ = "America/Chicago"
Z = ZoneInfo(TZ)
DAY = date(2000, 10, 16)                    # a Monday


def at(h, m=0, d=DAY):
    return datetime.combine(d, time(h, m), Z)


def placed(entries):
    return {e.task.title: (e.starts.strftime("%H:%M") if e.starts else None) for e in entries}


def test_urgent_work_goes_first_around_meetings_and_lunch():
    entries = solve([Task(1, "someday", "task", 30),
                     Task(2, "overdue", "task", 30, priority=4, due=at(9, 0, date(2000, 10, 13))),
                     Task(3, "by noon", "task", 60, priority=3, due=at(12)),
                     Task(4, "review", "meeting", 60, fixed=at(9, 30))], DAY, TZ)
    got = placed(entries)
    assert got["overdue"] == "09:00" and got["review"] == "09:30" and got["Lunch"] == "13:00"
    assert got["by noon"] == "10:30"                                     # finishes before its deadline
    assert got["someday"] not in (None, "09:00", "09:30", "10:30", "11:00", "13:00", "13:30")


def test_overlapping_meetings_and_a_full_day_bump_the_least_important():
    items = [Task(10, "call A", "meeting", 60, fixed=at(15)), Task(11, "call B", "meeting", 60, fixed=at(15, 30))]
    items += [Task(i, f"t{i}", "task", 60, priority=3 if i < 5 else 1) for i in range(8)]
    got = placed(solve(items, DAY, TZ, now=at(12)))
    done = {k for k, v in got.items() if k.startswith("t") and v is not None}
    assert len(done) == 3 and done <= {f"t{i}" for i in range(5)}     # noon, 14:00, 16:30: urgent ones only
    assert all(got[k] >= "12:00" for k in done)                         # nothing before now


def test_after_hours_everything_waits_for_tomorrow():
    got = placed(solve([Task(1, "late", "task", 30, priority=4)], DAY, TZ, now=at(19)))
    assert got["late"] is None


@pytest.mark.db
def test_a_missed_task_is_marked_and_planned_again_with_higher_priority(db_url):
    owner = "vince.kaminski@enron.com"
    with connect(db_url) as conn:
        ingest_messages(conn, [Message("p/1.", "sent", datetime(2000, 10, 13, 15, tzinfo=UTC), owner,
                                       ("shirley.crenshaw@enron.com",), (), "Budget", "I will send the budget.")],
                        {owner})
        item = conn.execute("SELECT item_id FROM item_refs WHERE ref = 'p/1.'").fetchone()["item_id"]
        for statement, due in (("Send the budget", at(0, 0, date(2000, 10, 13))), ("Read the paper", None),
                               ("Book the room", at(11))):
            conn.execute("INSERT INTO beliefs (kind, actor, other, statement, due_at, valid, item_id, quote, "
                         "confidence) VALUES ('commitment', 'vince kaminski', 'shirley crenshaw', %s, %s, "
                         "tstzrange('2000-10-13 15:00+00', NULL), %s, %s, 0.9)", (statement, due, item, statement))
        conn.commit()
        people.build(conn)
        names = owner_names(conn, "kaminski-v")
        v1, first = plan_day(conn, DAY, TZ, names)
        conn.execute("UPDATE beliefs SET status = 'done' WHERE statement = 'Book the room'")
        v2, second = plan_day(conn, DAY, TZ, names, now=at(12))
    assert "kaminski-v" in names and "vince kaminski" in names
    assert placed(first)["Send the budget"] == "09:00" and v1 == 1        # overdue: first thing
    status = {(e.task.title, e.status) for e in second}
    assert v2 == 2 and ("Book the room", "done") in status and ("Send the budget", "missed") in status
    again = next(e for e in second if e.task.title == "Send the budget" and e.status == "planned")
    assert again.starts >= at(12) and "missed earlier today" in again.task.why
