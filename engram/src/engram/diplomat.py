"""Diplomat: the owner's secretary agrees a meeting time with another company's secretary, over HTTP
(docs/research/agent-roster-review.md §6: a small scripted demo; notes H §4 for the risks).

Agents talking to agents leak context-inappropriate information with no attacker present (ConfAIde, PrivacyLens,
AirGapAgent), and even a spec-compliant A2A exchange has open injection and exfiltration paths (A2ABreak). So the
two sides exchange no prose at all. A message is a fixed schema: a kind (propose, counter, accept, decline), the
topic the owner gave, a length, and at most three start times. The minimizer (D44) builds every outgoing message
from those fields alone, so no reason, calendar entry, name or note can leave, and it refuses a topic that
carries an address, a phone number or an amount. The other side's messages are untrusted: anything outside the
schema is dropped and reported, and a slot outside working hours or the next 30 days is refused. Negotiating is
code, with no model involved: accept the earliest offered slot that is free, else counter with this side's next
free slots, for at most four rounds. Every outgoing message, and the calendar event at the end, goes through the
gate, so the owner approves it on the page or the watch."""
from __future__ import annotations

import hmac
import json
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal

import httpx

from .act import Check, Gate, Tool
from .meeting import Event, free_slots, problem, when

Kind = Literal["propose", "counter", "accept", "decline"]
KINDS = ("propose", "counter", "accept", "decline")
FIELDS = {"conversation", "kind", "topic", "minutes", "slots"}
MAX_SLOTS, MAX_ROUNDS, HORIZON = 3, 4, timedelta(days=30)
PRIVATE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"                       # an address
                     r"|\+?\d[\d\s().-]{7,}\d"                          # a phone number
                     r"|[$₹€£]\s?\d|\b\d[\d,]*\s?(usd|inr|rs|lakh|crore)\b", re.I)   # an amount


class Refused(ValueError):
    """A message that must not be sent, or must not be believed."""


@dataclass(frozen=True)
class Message:
    conversation: str
    kind: Kind
    topic: str
    minutes: int
    slots: tuple[datetime, ...] = ()

    def wire(self) -> dict[str, Any]:
        return {"conversation": self.conversation, "kind": self.kind, "topic": self.topic, "minutes": self.minutes,
                "slots": [f"{s:%Y-%m-%dT%H:%M}" for s in self.slots]}

    @property
    def line(self) -> str:
        """What the owner is shown before it is sent."""
        times = "; ".join(when(s) for s in self.slots)
        return {"propose": f"propose '{self.topic}' ({self.minutes} min) at {times}",
                "counter": f"counter with {times}", "accept": f"accept {times}",
                "decline": "decline: no common time"}[self.kind]


def minimize(kind: Kind, conversation: str, topic: str, minutes: int, slots: Sequence[datetime]) -> Message:
    """D44: the only way an outgoing message is built. The schema is the whitelist; the topic may not carry
    contact details or amounts."""
    topic = " ".join(topic.split())[:80]
    if PRIVATE.search(topic):
        raise Refused("the topic carries contact details or an amount; say it without them")
    if kind not in KINDS or not 15 <= minutes <= 240:
        raise Refused("bad kind or length")
    return Message(conversation, kind, topic, minutes, tuple(slots)[:MAX_SLOTS])


def parse(raw: Any, now: datetime) -> tuple[Message, list[str]]:
    """The other side's message, believed only as far as the schema goes. Returns it and what was dropped."""
    if not isinstance(raw, dict):
        raise Refused("not a message")
    dropped = sorted(set(raw) - FIELDS)
    try:
        kind, minutes = raw["kind"], int(raw["minutes"])
        slots = tuple(datetime.fromisoformat(str(s)) for s in raw.get("slots", []))
    except (KeyError, TypeError, ValueError) as e:
        raise Refused(f"malformed message: {e}") from e
    if kind not in KINDS or not 15 <= minutes <= 240 or len(slots) > MAX_SLOTS:
        raise Refused("outside the protocol")
    for s in slots:
        if not now <= s <= now + HORIZON or problem(s, minutes, [], now):
            raise Refused(f"slot {s:%Y-%m-%d %H:%M} is outside working hours or the next 30 days")
    topic = " ".join(str(raw.get("topic", "")).split())[:80]
    return Message(str(raw.get("conversation", ""))[:64], kind, topic, minutes, slots), dropped


def answer(msg: Message, calendar: Sequence[Event], now: datetime) -> tuple[Kind, list[datetime]]:
    """Code, not a model: take the earliest offered slot that is free here, else offer this side's next free
    slots (from the earliest offered time on)."""
    if msg.kind in ("propose", "counter"):
        free = [s for s in sorted(msg.slots) if not problem(s, msg.minutes, calendar, now)]
        if free:
            return "accept", [free[0]]
        after = max(now, min(msg.slots)) if msg.slots else now
        return "counter", free_slots(calendar, after, msg.minutes, MAX_SLOTS)
    return msg.kind, list(msg.slots)


@dataclass
class Side:
    """One secretary: its owner's calendar, the gate its outgoing messages pass, and a transcript."""
    name: str
    calendar: list[Event]
    gate: Gate
    now: datetime
    log: list[str] = field(default_factory=list)

    def send(self, peer: str, msg: Message, post: Callable[[dict], dict], subject: str) -> dict | None:
        """Through the gate (the owner approves each message), then over the wire."""
        tool = Tool("diplomat.send", "external", post, preview=lambda a: f"to {peer}: {msg.line}")
        c: Check = self.gate.check(f"Agree a meeting time with {peer} about '{msg.topic}'", tool, msg.wire(),
                                   subject)
        self.log.append(f"{self.name} → {peer}: {msg.line}  [{c.reason}]")
        return post(msg.wire()) if c.allowed else None

    def book(self, slot: datetime, minutes: int, topic: str, peer: str, create: Callable[..., Any] | None,
             subject: str) -> bool:
        tool = Tool("calendar.create_event", "external", create or (lambda **a: "ok"),
                    preview=lambda a: f"calendar: '{topic}' with {peer} at {when(slot)}")
        args = {"event_name": topic, "participant_email": peer, "event_start": f"{slot:%Y-%m-%d %H:%M:%S}",
                "duration": str(minutes)}
        c = self.gate.check(f"Add the agreed meeting with {peer} to my calendar", tool, args, subject)
        self.log.append(f"{self.name} books {when(slot)}  [{c.reason}]")
        if c.allowed:
            tool.run(**args)
            self.calendar.append(Event(slot, minutes, topic))
        return c.allowed


def negotiate(me: Side, peer: str, post: Callable[[dict], dict], topic: str, minutes: int,
              create: Callable[..., Any] | None = None) -> datetime | None:
    """The initiating side: propose, then answer counters, for at most MAX_ROUNDS; book what is agreed."""
    conv = uuid.uuid4().hex[:12]
    subject = f"diplomat:{conv}"
    msg = minimize("propose", conv, topic, minutes, free_slots(me.calendar, me.now, minutes, MAX_SLOTS))
    for _ in range(MAX_ROUNDS):
        raw = me.send(peer, msg, post, subject)
        if raw is None:
            me.log.append(f"{me.name}: the owner did not approve; stopped")
            return None
        try:
            reply, dropped = parse(raw, me.now)
        except Refused as e:
            me.log.append(f"{me.name}: refused {peer}'s reply ({e})")
            return None
        if dropped:
            me.log.append(f"{me.name}: dropped fields {peer} added: {', '.join(dropped)}")
        me.log.append(f"{peer} → {me.name}: {reply.line}")
        if reply.kind == "accept" and reply.slots and reply.slots[0] in msg.slots:
            return reply.slots[0] if me.book(reply.slots[0], minutes, topic, peer, create, subject) else None
        if reply.kind == "decline":
            return None
        kind, slots = answer(reply, me.calendar, me.now)
        if kind == "accept":
            final = minimize("accept", conv, topic, minutes, slots)
            if me.send(peer, final, post, subject) is None:
                return None
            return slots[0] if me.book(slots[0], minutes, topic, peer, create, subject) else None
        if not slots:
            me.send(peer, minimize("decline", conv, topic, minutes, []), post, subject)
            return None
        msg = minimize(kind, conv, topic, minutes, slots)
    me.send(peer, minimize("decline", conv, topic, minutes, []), post, subject)
    return None


def respond(me: Side, peer: str, raw: Any) -> dict:
    """The answering side, for one incoming message: answer it through its own owner's gate."""
    msg, dropped = parse(raw, me.now)
    if dropped:
        me.log.append(f"{me.name}: dropped fields {peer} added: {', '.join(dropped)}")
    me.log.append(f"{peer} → {me.name}: {msg.line}")
    subject = f"diplomat:{msg.conversation}"
    if msg.kind == "accept":
        booked = msg.slots and me.book(msg.slots[0], msg.minutes, msg.topic, peer, None, subject)
        return minimize("accept" if booked else "decline", msg.conversation, msg.topic, msg.minutes,
                        msg.slots if booked else []).wire()
    if msg.kind == "decline":
        return msg.wire()
    kind, slots = answer(msg, me.calendar, me.now)
    out = minimize(kind if slots else "decline", msg.conversation, msg.topic, msg.minutes, slots)
    tool = Tool("diplomat.send", "external", lambda **a: a, preview=lambda a: f"to {peer}: {out.line}")
    c = me.gate.check(f"Answer {peer}'s meeting proposal about '{msg.topic}'", tool, out.wire(), subject)
    me.log.append(f"{me.name} → {peer}: {out.line}  [{c.reason}]")
    if not c.allowed:
        return minimize("decline", msg.conversation, msg.topic, msg.minutes, []).wire()
    if out.kind == "accept":
        me.book(out.slots[0], out.minutes, out.topic, peer, None, subject)
    return out.wire()


# ------------------------------------------------------------------------------------------------- the wire

def poster(url: str, token: str, name: str) -> Callable[[dict], dict]:
    """POST a message to the other secretary; a shared token, agreed out of band, is the pairing."""
    def post(message: dict) -> dict:
        r = httpx.post(f"{url.rstrip('/')}/diplomat", json=message, timeout=30,
                       headers={"Authorization": f"Bearer {token}", "X-Engram-Side": name})
        r.raise_for_status()
        return r.json()
    return post


def serve_peer(side: Side, token: str, port: int, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """The other company's secretary as a tiny HTTP endpoint (the demo's second brain). Only POST /diplomat with
    the shared token; one message in, one out."""
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            pass

        def _send(self, status: HTTPStatus, payload: Any) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            auth = self.headers.get("Authorization", "")
            if self.path != "/diplomat" or not hmac.compare_digest(auth.encode(), f"Bearer {token}".encode()):
                self._send(HTTPStatus.FORBIDDEN, {"error": "unknown secretary"})
                return
            n = int(self.headers.get("Content-Length") or 0)
            if n > 8192:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too long"})
                return
            try:
                peer = re.sub(r"[^\w.@-]", "", self.headers.get("X-Engram-Side", "peer"))[:40] or "peer"
                self._send(HTTPStatus.OK, respond(side, peer, json.loads(self.rfile.read(n) or b"{}")))
            except (Refused, ValueError) as e:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(e)})

    return ThreadingHTTPServer((host, port), Handler)


def peers(path: Path) -> dict[str, dict[str, str]]:
    """The known secretaries; a peer not in this file cannot be reached."""
    return json.loads(path.read_text()) if path.exists() else {}
