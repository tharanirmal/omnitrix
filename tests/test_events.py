import asyncio

import pytest

from omnitrix.core.board import Board
from omnitrix.core.clock import ClockStore
from omnitrix.core.events import EventBus, make_event

pytestmark = pytest.mark.db


async def test_duplicate_idempotency_keys_are_ignored(db, clock):
    bus = EventBus(db)
    key = "email.received:<abc@mehtatraders.example>"
    first = make_event("email.received", emitted_by="ingestion", clock=clock, idempotency_key=key)
    again = make_event("email.received", emitted_by="ingestion", clock=clock, idempotency_key=key)
    assert await bus.publish(first) is True
    assert await bus.publish(again) is False
    assert (await db.fetchrow("SELECT count(*) AS n FROM events"))["n"] == 1


async def test_catch_up_delivers_each_event_once_urgent_first(db, clock):
    bus = EventBus(db)
    seen = []

    async def handler(event):
        seen.append(event.type)

    bus.subscribe("planner", ["task.*", "meeting_request.*"], handler)
    for type_, priority in [("task.detected", "normal"), ("email.received", "normal"),
                            ("meeting_request.detected", "urgent")]:
        await bus.publish(make_event(type_, emitted_by="test", clock=clock, priority=priority))

    assert await bus.catch_up() == 2
    assert await bus.catch_up() == 0          # already done: nothing is delivered twice
    assert seen == ["meeting_request.detected", "task.detected"]


async def test_failed_deliveries_are_retried_then_given_up(db, clock):
    bus = EventBus(db)
    attempts = []

    async def flaky(event):
        attempts.append(1)
        raise RuntimeError("model timed out")

    bus.subscribe("writer", "draft.*", flaky)
    await bus.publish(make_event("draft.ready", emitted_by="test", clock=clock))
    for _ in range(5):
        await bus.catch_up()
    row = await db.fetchrow("SELECT status, attempts, last_error FROM event_deliveries")
    assert len(attempts) == 3 and row["status"] == "failed" and row["attempts"] == 3
    assert "model timed out" in row["last_error"]


async def test_run_wakes_on_notify(db, clock):
    bus = EventBus(db)
    got = asyncio.Event()

    async def handler(event):
        got.set()

    bus.subscribe("herald", "approval.requested", handler)
    ready = asyncio.Event()
    runner = asyncio.create_task(bus.run(on_ready=ready.set))
    await asyncio.wait_for(ready.wait(), 5)
    await bus.publish(make_event("approval.requested", emitted_by="guardian", clock=clock, priority="urgent"))
    await asyncio.wait_for(got.wait(), 5)
    bus.stop()
    await asyncio.wait_for(runner, 5)


async def test_story_follows_the_correlation_id(db, clock):
    bus = EventBus(db)
    e1 = make_event("email.received", emitted_by="ingestion", clock=clock, correlation_id="story_mr_4")
    e2 = make_event("meeting_request.detected", emitted_by="librarian", clock=clock, caused_by=e1)
    await bus.publish(e1)
    await bus.publish(e2)
    await bus.publish(make_event("task.detected", emitted_by="librarian", clock=clock))
    assert [e.event_id for e in await bus.story("story_mr_4")] == [e1.event_id, e2.event_id]


async def test_board_thread_and_clock_store(db, clock):
    board = Board(db, clock)
    await board.post("planner", "5 PM is free, slot held.", to_agent="writer", correlation_id="story_mr_4",
                     refs={"meeting_request_id": "mr_4"})
    await board.post("writer", "Draft ready.", to_agent="fact_checker", correlation_id="story_mr_4")
    thread = await board.thread("story_mr_4")
    assert [m.from_agent for m in thread] == ["planner", "writer"]

    store = ClockStore(db)
    await store.save(clock)
    assert (await store.load(clock.tz)).now() == clock.now()
