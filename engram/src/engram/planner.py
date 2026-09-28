"""Planner: the owner's open commitments become today's plan, and a missed task re-plans the rest of the day.

Models are bad at scheduling and solvers are good at it (H §3: frontier models reach 33-48% on NATURAL PLAN's
calendar tasks, while a solver-checked plan reaches ~94%). So the models' part ended at memory: they extracted the
commitments, meetings and times. Everything here is code. A transparent priority score comes from the deadline and
how much the owner deals with the other person. OR-Tools CP-SAT places tasks in 15-minute slots around fixed
meetings and protected time (lunch, personal time, never offered away). It prefers urgent and important tasks early,
penalises finishing after a deadline, and bumps what does not fit. Re-planning at a given `now` marks planned tasks
whose slot has passed while the commitment is still open as missed, then solves the rest of the day with them
included and raised one priority step."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import psycopg

from .judge import Judge, noul
from .memory import party_names

SLOT = 15                                   # minutes: the solver's grid
TASK_MINUTES = {"commitment": 30}           # until the judge estimates durations (D16)
MEETING_MINUTES = 60
WORK = (time(9, 0), time(18, 0))            # the owner's working day, local time
PROTECTED = (("Lunch", time(13, 0), time(14, 0)),)
IMPORTANT = 50                              # items exchanged with a person that make them "important"
TODO = noul("todo", "Is this something the owner personally has to do, that they could set time aside for in their "
                    "day (send, write, call, review, prepare, decide, attend...)? Answer no if someone else has to "
                    "act, if it only states where someone will be or what they are registered for, or if it is an "
                    "intention with nothing to do yet.")
TODO_PASS = 0.5                             # the judge's P(yes) a commitment needs to enter the plan
PLAN_LOCK = 0x656E706C                       # advisory lock with the day: plans of one day never interleave ('enpl')
UNDATED_DAYS = 14                           # an undated commitment stays on the list this long after it was made


@dataclass
class Task:
    belief: int | None
    title: str
    kind: str                               # task | meeting | protected
    minutes: int
    priority: int = 1                       # 1 low .. 4 overdue
    due: datetime | None = None
    fixed: datetime | None = None           # meetings and protected blocks: their start
    why: list[str] = field(default_factory=list)


@dataclass
class Entry:
    task: Task
    starts: datetime | None
    ends: datetime | None
    status: str = "planned"                 # planned | done | missed | bumped


def owner_names(conn: psycopg.Connection, mailbox: str) -> set[str]:
    """Every name beliefs use for the owner: the people entry's names and the mailbox id the extractor was given."""
    return party_names(conn, "owner") | {mailbox.lower()}


def tasks(conn: psycopg.Connection, day: date, tz: str, owner: set[str], missed: set[int] = frozenset(),
          judge: Judge | None = None) -> list[Task]:
    """Today's candidates: the owner's open commitments made by the end of the day (overdue ones included), and
    the meetings set for today at a stated time. With a judge, only commitments it reads as the owner's own to-do
    (D13/D14; answers are cached in the ledger, so a re-plan asks nothing again)."""
    zone = ZoneInfo(tz)
    start, end = datetime.combine(day, time.min, zone), datetime.combine(day + timedelta(days=1), time.min, zone)
    weight = {r["n"]: r["n_items"] for r in conn.execute(
        "SELECT unnest(array_append(aliases, key)) AS n, n_items FROM people")}
    out: list[Task] = []
    for b in conn.execute(
            "SELECT id, kind, actor, other, statement, due_at, when_text FROM current_beliefs WHERE status = 'open' "
            "AND trust <> 'quarantined' AND lower(valid) < %(end)s AND ("
            "  (kind = 'commitment' AND actor = ANY(%(owner)s) AND (due_at >= %(start)s - interval '7 days' OR "
            "   (due_at IS NULL AND lower(valid) >= %(start)s - make_interval(days => %(undated)s)))) OR "
            "  (kind = 'meeting' AND due_at >= %(start)s AND due_at < %(end)s AND (actor = ANY(%(owner)s) OR "
            "   other = ANY(%(owner)s) OR statement ILIKE ANY(%(like)s)))) ORDER BY id",
            {"start": start, "end": end, "owner": sorted(owner), "undated": UNDATED_DAYS,
             "like": [f"%{n}%" for n in sorted(owner) if len(n) > 3]}):
        due = b["due_at"].astimezone(zone) if b["due_at"] else None
        if b["kind"] == "meeting":
            if due is None or due.time() == time.min:                 # a date without a time is not a block
                continue
            out.append(Task(b["id"], b["statement"], "meeting", MEETING_MINUTES, fixed=due, why=["meeting"]))
            continue
        if judge is not None and not _todo(judge, b):
            continue
        if due is not None and due.time() == time.min:                   # a date alone: by the end of that day
            due = datetime.combine(due.date(), WORK[1], zone)
        t = Task(b["id"], b["statement"], "task", TASK_MINUTES["commitment"], due=due)
        if due is None:
            t.why.append("no deadline")
        elif due < start:
            t.priority = 4
            t.why.append(f"overdue since {due:%a %d %b}")
        elif due < end:
            t.priority = 3
            t.why.append(f"due today {due:%H:%M}")
        elif due < end + timedelta(days=2):
            t.priority = 2
            t.why.append(f"due {due:%a}")
        if weight.get(b["other"].lower(), 0) >= IMPORTANT:
            t.priority = min(4, t.priority + 1)
            t.why.append(f"for {b['other'].title()} (important contact)")
        if b["id"] in missed:
            t.priority = min(4, t.priority + 1)
            t.why.append("missed earlier today")
        out.append(t)
    return out


def todo_state(b: dict) -> str:
    """What `todo` reads: one commitment, with its parties and time words."""
    return f"Commitment by {b['actor']} to {b['other'] or '-'}: {b['statement']} (when: {b['when_text'] or '-'})"


def _todo(judge: Judge, b: dict) -> bool:
    """The cascade (S1, then S2 when S1 is unsure): zero-shot, the small judge cannot tell a to-do from a status
    (P(yes) 0.16-0.32 on everything), while the 14B separates the clear cases. No valid answer keeps the task."""
    v = judge.ask(TODO, todo_state(b), f"belief:{b['id']}")
    return not v.value or v.probs.get("yes", 0.0) >= TODO_PASS


def solve(items: list[Task], day: date, tz: str, now: datetime | None = None, seconds: float = 2.0) -> list[Entry]:
    """Place tasks in today's free slots from `now` (or the start of the working day). Meetings and protected
    blocks stay where they are; tasks that do not fit are bumped."""
    from ortools.sat.python import cp_model

    zone = ZoneInfo(tz)
    day0 = datetime.combine(day, WORK[0], zone)
    close = datetime.combine(day, WORK[1], zone)
    begin = max(day0, now.astimezone(zone)) if now else day0
    slot = lambda dt: int((dt - day0).total_seconds() // 60) // SLOT              # noqa: E731
    at = lambda s: day0 + timedelta(minutes=s * SLOT)                            # noqa: E731
    lo, hi = -(-int((begin - day0).total_seconds() // 60) // SLOT), slot(close)
    blocks = [*items, *(Task(None, name, "protected", int((datetime.combine(day, b, zone) - datetime.combine(
        day, a, zone)).total_seconds() // 60), fixed=datetime.combine(day, a, zone), why=["protected"])
        for name, a, b in PROTECTED)]

    m = cp_model.CpModel()
    intervals, placed, score = [], {}, []
    busy: list[list[int]] = []                                  # fixed blocks may overlap each other: merge them
    for s, size in sorted((slot(t.fixed), max(1, -(-t.minutes // SLOT))) for t in blocks if t.fixed is not None):
        if busy and s <= busy[-1][1]:
            busy[-1][1] = max(busy[-1][1], s + size)
        else:
            busy.append([s, s + size])
    for k, (a, b) in enumerate(busy):
        if b > lo and a < hi:                                   # still ahead (or running)
            intervals.append(m.new_fixed_size_interval_var(a, b - a, f"busy{k}"))
    for i, t in enumerate(blocks):
        size = max(1, -(-t.minutes // SLOT))
        if t.fixed is not None or hi - lo < size:
            continue
        start = m.new_int_var(lo, hi - size, f"s{i}")
        on = m.new_bool_var(f"on{i}")
        intervals.append(m.new_optional_fixed_size_interval_var(start, size, on, f"t{i}"))
        placed[i] = (start, on, size)
        score.append(on * (1000 * t.priority))                                    # doing it at all matters most
        score.append(-start * t.priority)                                         # urgent things early
        if t.due is not None and t.due.astimezone(zone) < close:
            late = m.new_int_var(0, hi, f"late{i}")
            m.add(late >= start + size - max(slot(t.due.astimezone(zone)), lo)).only_enforce_if(on)
            score.append(-late * 20 * t.priority)                                 # finishing after the deadline
    m.add_no_overlap(intervals)
    m.maximize(sum(score))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_workers = 4
    ok = solver.solve(m) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    out = []
    for i, t in enumerate(blocks):
        if t.fixed is not None:
            out.append(Entry(t, t.fixed, t.fixed + timedelta(minutes=t.minutes)))
        elif ok and i in placed and solver.value(placed[i][1]):
            s = solver.value(placed[i][0])
            out.append(Entry(t, at(s), at(s + placed[i][2])))
        else:
            out.append(Entry(t, None, None, "bumped"))
    return sorted(out, key=lambda e: (e.starts is None, e.starts or day0, e.task.title))


def plan_day(conn: psycopg.Connection, day: date, tz: str, owner: set[str], now: datetime | None = None,
             judge: Judge | None = None) -> tuple[int, list[Entry]]:
    """Plan (or re-plan at `now`) the day and store it as a new version. Planned tasks of the previous version
    whose slot ended before `now` while the commitment is still open are marked missed and planned again."""
    conn.execute("SELECT pg_advisory_xact_lock(%s, %s)", (PLAN_LOCK, day.toordinal()))   # one planner per day
    prev = conn.execute("SELECT coalesce(max(version), 0) AS v FROM plan_entries WHERE day = %s",
                        (day,)).fetchone()["v"]
    missed: set[int] = set()
    kept: list[Entry] = []
    if prev and now is not None:
        for r in conn.execute(
                "SELECT e.*, b.status AS bstatus FROM plan_entries e LEFT JOIN beliefs b ON b.id = e.belief_id "
                "WHERE e.day = %s AND e.version = %s AND e.starts IS NOT NULL AND e.ends <= %s",
                (day, prev, now)).fetchall():
            if r["kind"] != "task":
                continue
            status = "done" if r["bstatus"] == "done" else "missed"
            if status == "missed":
                missed.add(r["belief_id"])
            kept.append(Entry(Task(r["belief_id"], r["title"], "task", 0, why=[r["why"]]), r["starts"], r["ends"],
                              status))
    past = {e.task.belief for e in kept if e.status == "done"}
    todo = [t for t in tasks(conn, day, tz, owner, missed, judge) if t.belief not in past]
    entries = sorted(kept + solve(todo, day, tz, now), key=lambda e: (e.starts is None, e.starts or now, e.status))
    version = prev + 1
    with conn.cursor() as cur:
        for e in entries:
            cur.execute("INSERT INTO plan_entries (day, version, belief_id, title, starts, ends, kind, status, why) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (day, version, e.task.belief, e.task.title, e.starts, e.ends, e.task.kind, e.status,
                         "; ".join(e.task.why)))
    conn.commit()
    return version, entries
