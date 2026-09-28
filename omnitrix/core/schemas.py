"""The shared formats. Every agent, tool and screen builds against these - change them only by bumping
`version` and telling the whole team. `omnitrix schemas export` writes them to schemas/*.schema.json."""
from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Priority = Literal["low", "normal", "high", "urgent"]
PRIORITY_RANK: dict[str, int] = {"low": 0, "normal": 1, "high": 2, "urgent": 3}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------------------------- events

EVENT_TYPES: dict[str, str] = {
    # input
    "email.received": "A new email arrived in the inbox",
    "file.added": "A file was added to a watched folder",
    "note.changed": "An Obsidian note was created or changed (including ticked tasks)",
    "voice_note.transcribed": "A voice note was turned into text",
    # knowledge
    "document.ingested": "A source was parsed, chunked and embedded",
    "entity.discovered": "A new person, organization or project was found",
    # work
    "task.detected": "The Librarian found a task",
    "task.completed": "A task was done (tick, evidence or user)",
    "task.missed": "A task's slot passed and it was not done",
    "meeting_request.detected": "Someone asked to meet",
    "meeting_request.checked": "The Planner checked the calendar for a meeting request",
    "plan.updated": "A new version of a day plan was made",
    # memory
    "promise.detected": "A promise was found (by you or to you)",
    "promise.due_soon": "A promise is close to its deadline",
    "promise.overdue": "A promise passed its deadline",
    "decision.detected": "A decision was found",
    "decision.conflict_found": "Something contradicts an earlier decision",
    # drafts
    "draft.ready": "The Writer finished a draft",
    "draft.checked": "The Fact Checker reviewed a draft",
    # control
    "approval.requested": "A risky action is waiting for the user",
    "approval.approved": "The user approved an action",
    "approval.rejected": "The user rejected an action",
    "approval.expired": "An approval request timed out",
    "security.threat_blocked": "The Guardian blocked something dangerous",
    # system
    "clock.tick": "One minute passed on the demo clock",
    "clock.jumped": "The demo clock was fast-forwarded or moved",
    "schedule.morning_brief": "Time for the morning brief",
    "schedule.evening_wrap": "Time for the evening wrap-up",
}


class Subject(Strict):
    kind: str
    id: str


class Event(Strict):
    """Something that happened. Small payloads (IDs + key facts), past-tense names, never modified."""

    event_id: str
    type: str
    version: int = 1
    occurred_at: datetime                 # from the demo clock
    emitted_by: str                       # agent or component name
    idempotency_key: str                  # same key -> same event; duplicates are ignored
    correlation_id: str | None = None     # the story this event belongs to
    caused_by: str | None = None          # event_id that led to this one
    subject: Subject | None = None
    priority: Priority = "normal"
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(f"unknown event type {v!r}; add it to EVENT_TYPES first")
        return v


# ---------------------------------------------------------------------------------------------- tasks

ActionType = Literal["send", "call", "meet", "review", "write", "decide", "pay", "buy", "book", "other"]
TaskStatus = Literal["needs_confirmation", "todo", "blocked", "scheduled", "in_progress", "done", "missed",
                     "dropped"]


class TaskCandidate(Strict):
    """What the Librarian's model extracts from text - only what the text says. Kept small on purpose:
    small local models do much better with a short, flat format."""

    title: str = Field(description="Short action, verb first: 'Send quote to Mehta'", max_length=120)
    action_type: ActionType
    due_text: str | None = Field(None, description="The exact words used for the deadline, if any")
    due_at: datetime | None = Field(None, description="Best guess of the deadline as ISO-8601 with offset")
    people: list[str] = Field(default_factory=list, description="Names of people involved")
    waiting_on_text: str | None = Field(None, description="Anything the task is blocked by")
    evidence_quote: str = Field(description="The exact sentence the task came from")
    confidence: float = Field(ge=0, le=1)


class TaskCandidateList(Strict):
    tasks: list[TaskCandidate]


class TaskSource(Strict):
    source_id: str
    email_id: str | None = None
    evidence_quote: str


class TaskPeople(Strict):
    owner: str = "me"                    # 'me' or an entity id
    requested_by: str | None = None      # entity id
    related: list[str] = Field(default_factory=list)


class TaskTiming(Strict):
    due_at: datetime | None = None
    due_type: Literal["hard", "soft", "none"] = "none"
    earliest_start: datetime | None = None


class TaskEffort(Strict):
    estimate_minutes: int = Field(30, ge=5)
    estimate_basis: str = "default"
    energy: Literal["focus", "admin", "any"] = "any"
    can_split: bool = False


class TaskPriority(Strict):
    score: int = Field(0, ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class TaskSchedule(Strict):
    plan_id: str
    plan_version: int
    start: datetime
    end: datetime
    flexible: bool = True


class TaskHistoryEntry(Strict):
    at: datetime
    status: TaskStatus
    by: str
    note: str | None = None


class Task(Strict):
    task_id: str
    title: str
    action_type: ActionType
    source: TaskSource
    people: TaskPeople = Field(default_factory=TaskPeople)
    timing: TaskTiming = Field(default_factory=TaskTiming)
    effort: TaskEffort = Field(default_factory=TaskEffort)
    priority: TaskPriority = Field(default_factory=TaskPriority)
    blocked_by: list[str] = Field(default_factory=list)   # task or promise ids
    schedule: TaskSchedule | None = None
    status: TaskStatus = "todo"
    times_missed: int = 0
    history: list[TaskHistoryEntry] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0, le=1)
    needs_confirmation: bool = False


# ----------------------------------------------------------------------------------- meeting requests

MeetingStatus = Literal["new", "checked", "held", "awaiting_approval", "accepted", "declined",
                        "counter_proposed", "expired"]


class Slot(Strict):
    start: datetime
    end: datetime


class Availability(Strict):
    free: bool
    conflicts: list[str] = Field(default_factory=list)       # calendar event ids
    alternatives: list[Slot] = Field(default_factory=list)


class MeetingRequest(Strict):
    meeting_request_id: str
    email_id: str
    requester_entity_id: str | None = None
    proposed_start: datetime | None = None
    proposed_end: datetime | None = None
    time_text: str | None = None          # exact words: "at 5 PM today", "4 PM London time"
    timezone: str | None = None           # if the requester named one
    topic: str | None = None
    link: str | None = None
    availability: Availability | None = None
    held_event_id: str | None = None
    status: MeetingStatus = "new"
    reply_email_id: str | None = None
    correlation_id: str | None = None


# ------------------------------------------------------------------------------------------ approvals

Risk = Literal["green", "yellow", "red"]
ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]


class ApprovalRequest(Strict):
    """What the Herald shows on the phone / watch. The one-time token is only ever sent to the device;
    the database keeps its hash."""

    approval_id: str
    requested_by_agent: str
    action: str                           # the tool, e.g. "email.reply_in_thread"
    risk: Risk
    title: str
    summary: str
    preview: str | None = None
    buttons: list[str] = Field(default_factory=lambda: ["approve", "reject"])
    token: str | None = None
    expires_at: datetime
    status: ApprovalStatus = "pending"
    correlation_id: str | None = None


# ------------------------------------------------------------------------------------- board messages

class BoardMessage(Strict):
    """Agents talking to each other - shown live as the agent chat room."""

    message_id: str
    from_agent: str
    to_agent: str | None = None           # None = everyone
    correlation_id: str | None = None
    text: str
    refs: dict[str, str] = Field(default_factory=dict)
    at: datetime                          # demo clock


EXPORTED: dict[str, type[BaseModel]] = {
    "event": Event,
    "task_candidate": TaskCandidate,
    "task_candidate_list": TaskCandidateList,
    "task": Task,
    "meeting_request": MeetingRequest,
    "approval_request": ApprovalRequest,
    "board_message": BoardMessage,
}


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema with every $ref resolved in place, for Ollama's `format` (structured output)."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                target = copy.deepcopy(defs[node["$ref"].split("/")[-1]])
                rest = {k: v for k, v in node.items() if k != "$ref"}
                return resolve({**target, **rest})
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)
