"""Task priority: a plain formula, not AI - predictable, testable, and every point has a reason.

    deadline closeness   up to 40
    who is asking        up to 30   (entity importance 0-3)
    money involved       up to 15
    missed before        +7 each, up to 21
    hard deadline        +10
    ---------------------------------
    clamped to 0..100

Example: due in 1 day (+35), key client (+30), ₹20 L deal (+15), missed once (+7) = 87.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from omnitrix.core.schemas import TaskPriority

# (due within, points) - first match wins
DEADLINE_BANDS: list[tuple[timedelta, int]] = [
    (timedelta(hours=4), 38),
    (timedelta(days=1), 35),
    (timedelta(days=2), 28),
    (timedelta(days=3), 22),
    (timedelta(days=7), 12),
]
OVERDUE_POINTS = 40
FAR_DEADLINE_POINTS = 5

IMPORTANCE_POINTS = {0: 0, 1: 10, 2: 20, 3: 30}
IMPORTANCE_LABEL = {0: "low-priority contact", 1: "a regular contact", 2: "an important contact", 3: "a key contact"}

LAKH = 100_000
MISSED_POINTS, MISSED_CAP = 7, 21
HARD_DEADLINE_POINTS = 10


@dataclass
class ScoreInput:
    now: datetime
    due_at: datetime | None = None
    hard_deadline: bool = False
    requester_name: str | None = None
    requester_importance: int = 0          # entities.importance
    money_inr: float | None = None         # value of the linked deal / payment
    times_missed: int = 0


def score_task(inp: ScoreInput) -> TaskPriority:
    points = 0
    reasons: list[str] = []

    def add(n: int, reason: str) -> None:
        nonlocal points
        if n:
            points += n
            reasons.append(f"{reason} (+{n})")

    if inp.due_at is not None:
        left = inp.due_at - inp.now
        if left <= timedelta(0):
            add(OVERDUE_POINTS, f"overdue by {_human(-left)}")
        else:
            band = next((pts for limit, pts in DEADLINE_BANDS if left <= limit), FAR_DEADLINE_POINTS)
            add(band, f"deadline in {_human(left)}")
        if inp.hard_deadline:
            add(HARD_DEADLINE_POINTS, "hard deadline")

    importance = max(0, min(3, inp.requester_importance))
    if inp.requester_name or importance:
        who = f" {inp.requester_name}" if inp.requester_name else ""
        add(IMPORTANCE_POINTS[importance], f"requested by {IMPORTANCE_LABEL[importance]}{who}")

    if inp.money_inr:
        amount = _rupees(inp.money_inr)
        if inp.money_inr >= 10 * LAKH:
            add(15, f"linked to {amount} deal")
        elif inp.money_inr >= LAKH:
            add(10, f"linked to {amount} deal")
        else:
            add(5, f"involves {amount}")

    if inp.times_missed:
        n = inp.times_missed
        add(min(MISSED_CAP, MISSED_POINTS * n), f"missed {'once' if n == 1 else f'{n} times'} already")

    return TaskPriority(score=max(0, min(100, points)), reasons=reasons)


def _human(d: timedelta) -> str:
    minutes = int(d.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} h"
    days = round(hours / 24)
    return f"{days} day" if days == 1 else f"{days} days"


def _rupees(amount: float) -> str:
    if amount >= 1_00_00_000:
        return f"₹{amount / 1_00_00_000:g} Cr"
    if amount >= LAKH:
        return f"₹{amount / LAKH:g} L"
    return f"₹{amount:,.0f}"
