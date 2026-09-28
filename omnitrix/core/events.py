"""The event bus: events are rows in Postgres, and LISTEN/NOTIFY wakes subscribers instantly.

- publish() stores the event; a repeated idempotency_key is ignored, so the same email never becomes
  two events. The NOTIFY goes out when the transaction commits.
- Subscribers name themselves (the consumer) and the event types they want ("task.*" works).
- Each (event, consumer) pair is claimed in event_deliveries before the handler runs, so a crash,
  a restart or a duplicate NOTIFY never runs a handler twice for the same event. Failed deliveries
  are retried up to MAX_ATTEMPTS.
- On start, run() first catches up on stored events the consumer has not handled yet.
"""
from __future__ import annotations

import asyncio
import fnmatch
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .clock import Clock
from .db import Database
from .ids import new_id
from .schemas import PRIORITY_RANK, Event, Priority, Subject

log = logging.getLogger(__name__)

CHANNEL = "omnitrix_events"
MAX_ATTEMPTS = 3

Handler = Callable[[Event], Awaitable[None]]

_PRIORITY_ORDER = "CASE e.priority " + " ".join(
    f"WHEN '{p}' THEN {r}" for p, r in PRIORITY_RANK.items()) + " END DESC"


def make_event(type: str, *, emitted_by: str, clock: Clock, idempotency_key: str | None = None,
               correlation_id: str | None = None, caused_by: Event | str | None = None,
               subject: tuple[str, str] | None = None, priority: Priority = "normal",
               payload: dict[str, Any] | None = None) -> Event:
    """Build an event. Without an idempotency_key the event is unique; pass one whenever the same input
    could be seen twice (e.g. f"email.received:{message_id}")."""
    event_id = new_id("event")
    parent = caused_by if isinstance(caused_by, Event) else None
    return Event(
        event_id=event_id,
        type=type,
        occurred_at=clock.now(),
        emitted_by=emitted_by,
        idempotency_key=idempotency_key or event_id,
        correlation_id=correlation_id or (parent.correlation_id if parent else None),
        caused_by=parent.event_id if parent else caused_by,
        subject=Subject(kind=subject[0], id=subject[1]) if subject else None,
        priority=priority,
        payload=payload or {},
    )


def _row_to_event(row: dict) -> Event:
    subject = Subject(kind=row["subject_kind"], id=row["subject_id"]) if row["subject_kind"] else None
    return Event(event_id=row["id"], type=row["type"], version=row["version"], occurred_at=row["occurred_at"],
                 emitted_by=row["emitted_by"], idempotency_key=row["idempotency_key"],
                 correlation_id=row["correlation_id"], caused_by=row["caused_by"], subject=subject,
                 priority=row["priority"], payload=row["payload"])


@dataclass
class Subscription:
    consumer: str
    patterns: tuple[str, ...]
    handler: Handler

    def wants(self, event_type: str) -> bool:
        return any(fnmatch.fnmatchcase(event_type, p) for p in self.patterns)


class EventBus:
    def __init__(self, db: Database):
        self.db = db
        self.subscriptions: list[Subscription] = []
        self._stop = asyncio.Event()

    # ------------------------------------------------------------------------------------- publishing

    async def publish(self, event: Event, conn: psycopg.AsyncConnection | None = None) -> bool:
        """Store and announce an event. Returns False if an event with the same idempotency_key already
        exists. Pass `conn` to publish inside the caller's transaction."""
        sql = ("INSERT INTO events (id, type, version, occurred_at, emitted_by, idempotency_key, correlation_id, "
               "caused_by, subject_kind, subject_id, priority, payload) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
               "ON CONFLICT (idempotency_key) DO NOTHING RETURNING id")
        params = (event.event_id, event.type, event.version, event.occurred_at, event.emitted_by,
                  event.idempotency_key, event.correlation_id, event.caused_by,
                  event.subject.kind if event.subject else None, event.subject.id if event.subject else None,
                  event.priority, Jsonb(event.payload))

        async def _do(c: psycopg.AsyncConnection) -> bool:
            inserted = await (await c.execute(sql, params)).fetchone()
            if inserted:
                await c.execute("SELECT pg_notify(%s, %s)", (CHANNEL, event.event_id))
            return inserted is not None

        if conn is not None:
            return await _do(conn)
        async with self.db.connection() as c:
            return await _do(c)

    async def get(self, event_id: str) -> Event | None:
        row = await self.db.fetchrow("SELECT * FROM events WHERE id = %s", (event_id,))
        return _row_to_event(row) if row else None

    async def story(self, correlation_id: str) -> list[Event]:
        rows = await self.db.fetch("SELECT * FROM events WHERE correlation_id = %s ORDER BY recorded_at",
                                   (correlation_id,))
        return [_row_to_event(r) for r in rows]

    # ------------------------------------------------------------------------------------ subscribing

    def subscribe(self, consumer: str, patterns: str | list[str], handler: Handler) -> None:
        if isinstance(patterns, str):
            patterns = [patterns]
        self.subscriptions.append(Subscription(consumer, tuple(patterns), handler))

    async def deliver(self, event: Event) -> None:
        """Run every interested subscriber once for this event."""
        for sub in self.subscriptions:
            if sub.wants(event.type):
                await self._deliver_one(sub, event)

    async def _claim(self, event_id: str, consumer: str) -> bool:
        row = await self.db.fetchrow(
            "INSERT INTO event_deliveries (event_id, consumer, status) VALUES (%s, %s, 'processing') "
            "ON CONFLICT (event_id, consumer) DO UPDATE "
            "SET status = 'processing', attempts = event_deliveries.attempts + 1, updated_at = clock_timestamp() "
            "WHERE event_deliveries.status = 'failed' AND event_deliveries.attempts < %s "
            "RETURNING attempts", (event_id, consumer, MAX_ATTEMPTS))
        return row is not None

    async def _deliver_one(self, sub: Subscription, event: Event) -> None:
        if not await self._claim(event.event_id, sub.consumer):
            return
        try:
            await sub.handler(event)
        except Exception as e:  # noqa: BLE001 - a failing agent must not stop the bus
            log.exception("consumer %s failed on %s", sub.consumer, event.event_id)
            await self.db.execute(
                "UPDATE event_deliveries SET status = 'failed', last_error = %s, updated_at = clock_timestamp() "
                "WHERE event_id = %s AND consumer = %s", (f"{type(e).__name__}: {e}", event.event_id, sub.consumer))
        else:
            await self.db.execute(
                "UPDATE event_deliveries SET status = 'done', last_error = NULL, updated_at = clock_timestamp() "
                "WHERE event_id = %s AND consumer = %s", (event.event_id, sub.consumer))

    async def catch_up(self) -> int:
        """Deliver stored events that a subscriber has not finished (or may retry). Urgent first."""
        delivered = 0
        for sub in self.subscriptions:
            rows = await self.db.fetch(
                "SELECT e.* FROM events e LEFT JOIN event_deliveries d "
                "ON d.event_id = e.id AND d.consumer = %s "
                "WHERE (d.event_id IS NULL OR (d.status = 'failed' AND d.attempts < %s)) "
                f"ORDER BY {_PRIORITY_ORDER}, e.recorded_at", (sub.consumer, MAX_ATTEMPTS))
            for row in rows:
                if sub.wants(row["type"]):
                    await self._deliver_one(sub, _row_to_event(row))
                    delivered += 1
        return delivered

    async def run(self, on_ready: Callable[[], None] | None = None) -> None:
        """Catch up, then deliver new events as they are announced, until stop() is called."""
        async with await psycopg.AsyncConnection.connect(self.db.url, autocommit=True) as listener:
            await listener.execute(f"LISTEN {CHANNEL}")
            await self.catch_up()
            if on_ready:
                on_ready()
            while not self._stop.is_set():
                # a fresh generator each second, so stop() is noticed promptly
                async for note in listener.notifies(timeout=1.0):
                    event = await self.get(note.payload)
                    if event:
                        await self.deliver(event)
                    if self._stop.is_set():
                        break

    def stop(self) -> None:
        self._stop.set()


async def tail(db: Database, since: datetime | None = None) -> list[Event]:
    """Recent events, oldest first (for the CLI and the dashboard timeline)."""
    rows = await db.fetch("SELECT * FROM events WHERE (%s::timestamptz IS NULL OR recorded_at >= %s) "
                          "ORDER BY recorded_at DESC LIMIT 50", (since, since))
    return [_row_to_event(r) for r in reversed(rows)]
