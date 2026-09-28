"""Feature 2, the smart meeting reply (docs/research/agent-roster-review.md §5): an email asks for a meeting; the
roles answer it as one pipeline, each step labelled with the role that takes it, so the page and the watch can
show the team at work.

Librarian: the `meeting_request` judge question decides whether this is a meeting request at all, then the large
model pulls out the topic, the time words and the length. Code resolves the time against the email's date (models
never do date arithmetic). Researcher: how much the owner deals with the sender (code). Planner: is the proposed
time inside working hours, clear of lunch and free on the calendar? If not, the next free slots, one per working
day (code). Writer: the large model drafts the reply in the owner's name. Fact Checker: code checks that the draft
names exactly the offered times and greets the right person; one redraft, then a plain template that passes by
construction. Guardian, Herald and Operator: the reply, and the calendar event when accepting, go through the gate
(both are external), so the owner approves on the page or the watch, and only then does anything leave."""
from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol

import dateparser

from .act import Check, Gate, Tool
from .judge import Judge
from .memory import MEETING

WORK_START, WORK_END = 9, 18                # WorkBench: meetings must not start before 9am or end after 6pm
PROTECTED = ((13, 14),)                     # lunch: never offered away (the planner's protected time)
SLOT = timedelta(minutes=30)
DEFAULT_MINUTES = 30
WB_NOW = datetime(2023, 11, 30, 10, 0)      # WorkBench's clock (its prompt: Thursday 2023-11-30), mid-morning
OFFER = 3                                   # slots offered when the proposed time does not work
EXTRACT_SYSTEM = ("You read one email that asks for a meeting. Copy `when` verbatim from the email: the exact words "
                  "it uses for the proposed day and time, or an empty string if it proposes none. `topic` is a short "
                  "name for the meeting. `minutes` is the length it asks for, or 0 if it does not say.")
EXTRACT_SCHEMA = {"type": "object", "required": ["topic", "when", "minutes"],
                  "properties": {"topic": {"type": "string"}, "when": {"type": "string"},
                                 "minutes": {"type": "integer"}}}
WRITE_SYSTEM = ("You write short, friendly work emails in the owner's name. Plain text, no subject line, at most "
                "four sentences, signed with the owner's first name. Mention no day or time except the ones given, "
                "written exactly as given.")
TIME_WORDS = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)|\b\d{1,2}:\d{2}\b|\b(monday|tuesday|wednesday|"
                        r"thursday|friday|saturday|sunday|tomorrow|today|tonight)\b", re.I)

CLOCK = re.compile(r"\d\s*(am|pm|a\.m\.|p\.m\.)|\d:\d{2}|\bnoon\b", re.I)   # an unambiguous clock time

Decision = Literal["accept", "propose", "not_meeting"]


class LLM(Protocol):
    def generate_json(self, model: str, system: str, user: str, schema: dict, max_tokens: int = 600) -> dict: ...
    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None, fmt: dict | None = None,
             think: bool = False, max_tokens: int = 1024) -> dict: ...


@dataclass(frozen=True)
class Email:
    email_id: str
    sender: str
    subject: str
    sent: datetime
    body: str

    @property
    def first_name(self) -> str:
        return re.split(r"[._\-]", self.sender.split("@")[0])[0].title()


@dataclass(frozen=True)
class Event:
    start: datetime
    minutes: int
    name: str = ""

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.minutes)


@dataclass
class Step:
    role: str                               # the roster role that took this step
    what: str
    ms: float


@dataclass
class Proposal:
    email: Email
    decision: Decision = "not_meeting"
    p_meeting: float = 0.0
    topic: str = ""
    when_words: str = ""
    proposed: datetime | None = None
    minutes: int = DEFAULT_MINUTES
    why: str = ""                           # why the proposed time does or does not work
    slots: list[datetime] = field(default_factory=list)    # the accepted time, or the times offered
    contact: str = ""                       # how much the owner deals with the sender
    reply: str = ""
    drafted_by: str = ""                    # 'model' | 'model, redrafted' | 'template'
    steps: list[Step] = field(default_factory=list)

    @property
    def headline(self) -> str:
        """One line for the watch: who, when, and whether the owner is free."""
        if self.decision == "accept":
            return f"{self.email.first_name}: {when(self.slots[0])}, you're free"
        if self.decision == "propose":
            return f"{self.email.first_name}: {self.why}; offer {len(self.slots)} other times"
        return f"{self.email.first_name}: not a meeting request"

    def actions(self) -> list[tuple[str, dict[str, str]]]:
        """What the Operator would do: always reply in the thread; add the event only when accepting."""
        if self.decision == "not_meeting":
            return []
        out = [("email.reply_email", {"email_id": self.email.email_id, "body": self.reply})]
        if self.decision == "accept":
            out.append(("calendar.create_event", {"event_name": self.topic or self.email.subject,
                                                  "participant_email": self.email.sender,
                                                  "event_start": f"{self.slots[0]:%Y-%m-%d %H:%M:%S}",
                                                  "duration": str(self.minutes)}))
        return out


def when(dt: datetime) -> str:
    """How a time is written in the reply, and checked: 'Tuesday 5 December at 2:00 PM'."""
    return f"{dt:%A} {dt.day} {dt:%B} at {dt.hour % 12 or 12}:{dt:%M} {'AM' if dt.hour < 12 else 'PM'}"


# ---------------------------------------------------------------------------------------------- the pipeline

def propose(email: Email, judge: Judge, llm: LLM, model: str, events: Sequence[Event], now: datetime,
            contacts: int = 0, owner: str = "Sam") -> Proposal:
    """Everything up to the gate: decide, find the time, draft and check the reply. Nothing is sent here."""
    pr = Proposal(email)

    def step(role: str, t0: float, what: str) -> None:
        pr.steps.append(Step(role, what, round((time.monotonic() - t0) * 1000)))

    t0 = time.monotonic()
    text = f"Subject: {email.subject}\nFrom: {email.sender}\n\n{email.body}"
    v = judge.ask(MEETING, text, f"email:{email.email_id}")
    pr.p_meeting = v.probs.get("yes", 0.0)
    if v.value != "yes":
        step("Librarian", t0, f"not a meeting request (p={pr.p_meeting:.2f}, {v.tier})")
        return pr
    x = llm.generate_json(model, EXTRACT_SYSTEM, text, EXTRACT_SCHEMA)
    pr.topic, pr.when_words = str(x.get("topic", "")).strip(), str(x.get("when", "")).strip()
    asked = int(x.get("minutes") or 0)
    pr.minutes = asked if 15 <= asked <= 240 else DEFAULT_MINUTES
    pr.proposed = resolve(pr.when_words, email.sent) if pr.when_words.lower() in email.body.lower() else None
    step("Librarian", t0, f"meeting request (p={pr.p_meeting:.2f}, {v.tier}): '{pr.topic}', "
                          f"time words '{pr.when_words or '-'}' → {when(pr.proposed) if pr.proposed else 'unclear'}")

    t0 = time.monotonic()
    pr.contact = f"{contacts} emails and events with {email.sender}" + (" (a frequent contact)" if contacts >= 5
                                                                        else "")
    step("Researcher", t0, pr.contact)

    t0 = time.monotonic()
    pr.why = problem(pr.proposed, pr.minutes, events, now)
    if not pr.why:
        pr.decision, pr.slots = "accept", [pr.proposed]
        step("Planner", t0, f"{when(pr.proposed)} is free for {pr.minutes} min")
    else:
        after = max(now, pr.proposed) if pr.proposed and pr.proposed > now else now
        pr.decision, pr.slots = "propose", free_slots(events, after, pr.minutes, OFFER)
        step("Planner", t0, f"{pr.why}; offering {', '.join(when(s) for s in pr.slots)}")

    t0 = time.monotonic()
    if pr.decision == "propose" and not pr.slots:               # fully booked: ask them to suggest a time
        pr.why += "; no free time in the next 30 days"
    days = {s.date() for s in pr.slots} | ({pr.proposed.date()} if pr.proposed else set())
    pr.reply, pr.drafted_by = write(llm, model, pr, owner, [e.name for e in events if e.start.date() in days])
    step("Writer", t0, f"drafted ({pr.drafted_by})")
    step("Fact Checker", t0, f"the reply names exactly the offered times and greets {email.first_name}"
         if pr.drafted_by != "template" else "both drafts failed the check: the plain template went out instead")
    return pr


def resolve(words: str, sent: datetime) -> datetime | None:
    """The moment the email's time words mean, read from the email's own date; None without an unambiguous clock
    time (dateparser reads a bare "at 3" as the email's own time of day, so a bare hour is not trusted)."""
    if not words or not CLOCK.search(words):     # "tomorrow", or "at 3" (am or pm?): not a time to accept
        return None
    dt = dateparser.parse(words, settings={"RELATIVE_BASE": sent, "PREFER_DATES_FROM": "future"})
    return None if dt is None else dt.replace(tzinfo=None, second=0, microsecond=0)


def problem(start: datetime | None, minutes: int, events: Sequence[Event], now: datetime) -> str:
    """Why this time does not work ('' if it does)."""
    if start is None:
        return "no clear time proposed"
    end = start + timedelta(minutes=minutes)
    if start < now:
        return f"{when(start)} has passed"
    if start.weekday() >= 5:
        return f"{when(start)} is at the weekend"
    if start.hour < WORK_START or end > start.replace(hour=WORK_END, minute=0):
        return f"{when(start)} is outside working hours"
    for a, b in PROTECTED:
        if start < start.replace(hour=b, minute=0) and end > start.replace(hour=a, minute=0):
            return f"{when(start)} is in protected time"
    clash = next((e for e in events if start < e.end and end > e.start), None)
    return f"busy at {when(start)} ({clash.name or 'another event'})" if clash else ""


def free_slots(events: Sequence[Event], after: datetime, minutes: int, n: int) -> list[datetime]:
    """The first free slot on each of the next `n` working days (spread out, as a person would offer them)."""
    t = after.replace(second=0, microsecond=0)
    t += timedelta(minutes=(-t.minute) % 30)
    out: list[datetime] = []
    while len(out) < n and t < after + timedelta(days=30):
        if not problem(t, minutes, events, after) and (not out or t.date() != out[-1].date()):
            out.append(t)
            t = (t + timedelta(days=1)).replace(hour=WORK_START, minute=0)
            continue
        t += SLOT
        if t.hour >= WORK_END:
            t = (t + timedelta(days=1)).replace(hour=WORK_START, minute=0)
    return out


def write(llm: LLM, model: str, pr: Proposal, owner: str, private: Sequence[str] = ()) -> tuple[str, str]:
    """Writer drafts; Fact Checker checks; one redraft with the problems named; then the template. `private` are
    the owner's calendar entries: the Writer never sees why the owner is busy, and a draft naming one fails."""
    times = [when(s) for s in pr.slots]
    if not times:
        return template(pr, owner, times), "template"
    if pr.decision == "accept":
        ask = f"Accept the meeting about '{pr.topic}' at {times[0]} ({pr.minutes} minutes)."
    elif pr.proposed is None:
        ask = f"Agree to meet about '{pr.topic}' and offer these times: {'; '.join(times)}."
    else:
        reason = ("you are busy then" if pr.why.startswith("busy") else
                  pr.why.replace(when(pr.proposed), "the proposed time") if pr.proposed else pr.why)
        ask = (f"Say briefly that the proposed time does not work ({reason}; give no other detail) and offer these "
               f"times instead: {'; '.join(times)}.")
    user = (f"Owner: {owner}\nReply to {pr.email.first_name} ({pr.email.sender}), who wrote:\n"
            f"Subject: {pr.email.subject}\n{pr.email.body[:1500]}\n\nTask: {ask}")
    for attempt in range(2):
        text = llm.chat(model, [{"role": "system", "content": WRITE_SYSTEM}, {"role": "user", "content": user}],
                        max_tokens=300)["content"].strip()
        theirs = f"{pr.email.subject}\n{pr.topic}\n{pr.email.body}"
        problems = check(text, times, pr.email.first_name, theirs, private)
        if not problems:
            return text, "model" if attempt == 0 else "model, redrafted"
        user += f"\n\nYour draft had problems: {'; '.join(problems)}. Write it again."
    return template(pr, owner, times), "template"


def check(text: str, times: Sequence[str], name: str, theirs: str = "", private: Sequence[str] = ()) -> list[str]:
    """Fact Checker, in code: every offered time appears exactly as written; no other day or time does, except
    those the sender wrote themselves (declining "5 PM today" may name it, or a "Monday planning" topic); the reply
    greets the right person; and it names none of the owner's other calendar entries (data minimisation, D44; a
    one-word entry like "call" or "sync" is an everyday word, not a leak)."""
    text = re.sub(r"\s+", " ", text)                  # a non-breaking or doubled space is still the same time
    problems = [f"missing '{t}'" for t in times if t.lower() not in text.lower()]
    rest = text
    for t in times:
        rest = re.sub(re.escape(t), " ", rest, flags=re.I)
    said = {m.group(0).lower() for m in TIME_WORDS.finditer(theirs)}
    stray = sorted({m.group(0) for m in TIME_WORDS.finditer(rest) if m.group(0).lower() not in said})
    if stray:
        problems.append(f"mentions {', '.join(stray)}, which was not offered")
    if not re.search(rf"\b{re.escape(name)}\b", text, re.I):
        problems.append(f"does not greet {name}")
    leaked = sorted({p for p in private if (" " in p.strip() or len(p) > 5)       # "call", "sync": everyday words
                     and re.search(rf"\b{re.escape(p.strip())}\b", text, re.I)})
    if leaked:
        problems.append(f"reveals the owner's calendar ({', '.join(leaked)})")
    return problems


def template(pr: Proposal, owner: str, times: Sequence[str]) -> str:
    if pr.decision == "accept":
        return f"Hi {pr.email.first_name},\n\n{times[0]} works for me. See you then.\n\nBest,\n{owner}"
    listed = "\n".join(f"- {t}" for t in times)
    if not times:
        return (f"Hi {pr.email.first_name},\n\nI'm fully booked for the next few weeks. Could you suggest a time "
                f"that suits you, and I'll see what I can move?\n\nBest,\n{owner}")
    lead = "Happy to meet. Could we do one of these?" if pr.proposed is None else \
        "The proposed time doesn't work for me. Could we do one of these?"
    return f"Hi {pr.email.first_name},\n\n{lead}\n{listed}\n\nBest,\n{owner}"


# -------------------------------------------------------------------------------------------- carrying it out

def carry_out(pr: Proposal, tools: dict[str, Tool], gate: Gate, subject: str,
              on_step: Callable[[Step], None] | None = None) -> list[tuple[str, Check, Any]]:
    """Guardian checks each action (both are external, so the owner approves on the page or the watch); the
    Operator runs what is allowed. Nothing runs without its check."""
    request = (f"Reply to {pr.email.first_name}'s meeting request '{pr.email.subject}'"
               + (f" and add it to my calendar at {when(pr.slots[0])}" if pr.decision == "accept" else ""))
    out = []
    for name, args in pr.actions():
        t0 = time.monotonic()
        c = gate.check(request, tools[name], args, subject)
        result = tools[name].run(**args) if c.allowed else None
        s = Step("Operator" if c.allowed else "Guardian", f"{name}: {c.reason}" + (f" → {result}" if c.allowed
                                                                                   else ""),
                 round((time.monotonic() - t0) * 1000))
        pr.steps.append(s)
        if on_step:
            on_step(s)
        out.append((name, c, result))
    return out


# ------------------------------------------------------------------------------------------ WorkBench's world

def wb_email(email_id: str) -> Email:
    """An email from WorkBench's sandbox inbox (call inside `workbench.sandbox`)."""
    from src.tools.state import get_state

    df = get_state().emails
    rows = df[df["email_id"] == email_id]
    if rows.empty:
        raise LookupError(f"no email {email_id}")
    r = rows.iloc[0]
    return Email(email_id, r["sender/recipient"], r["subject"], datetime.fromisoformat(r["sent_datetime"]),
                 r["body"].replace("\\n", "\n"))


def wb_add_email(sender: str, subject: str, body: str, sent: datetime) -> Email:
    """Put a new incoming email in the sandbox inbox (a demo: 'Mehta asks for 5 PM today')."""
    import pandas as pd
    from src.tools._utils import generate_next_id  # type: ignore[import-not-found]
    from src.tools.state import get_state

    state = get_state()
    email_id = generate_next_id(state.emails, "email_id")
    row = {"email_id": email_id, "inbox/outbox": "inbox", "sender/recipient": sender, "subject": subject,
           "sent_datetime": f"{sent:%Y-%m-%d %H:%M:%S}", "body": body}
    state.emails = pd.concat([state.emails, pd.DataFrame([row])], ignore_index=True)
    return Email(email_id, sender, subject, sent, body)


def wb_calendar() -> list[Event]:
    from src.tools.state import get_state

    return [Event(datetime.fromisoformat(r["event_start"]), int(float(r["duration"])), r["event_name"])
            for _, r in get_state().calendar_events.iterrows()]


def wb_contacts(sender: str) -> int:
    from src.tools.state import get_state

    s = get_state()
    return int((s.emails["sender/recipient"] == sender).sum()
               + (s.calendar_events["participant_email"] == sender).sum())
