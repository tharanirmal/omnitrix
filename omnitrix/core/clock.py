"""The one clock every component reads. Never call datetime.now() elsewhere.

Modes:
  real    - wall-clock time
  offset  - wall-clock time shifted by `offset_s` (fast-forward keeps time flowing)
  frozen  - a fixed instant (repeatable tests and demo beats)

The state is a small JSON document stored in the `settings` table under `demo_clock`, so every
process sees the same time; `ClockStore` loads and saves it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

Mode = Literal["real", "offset", "frozen"]
SETTINGS_KEY = "demo_clock"


@dataclass
class ClockState:
    mode: Mode = "real"
    offset_s: float = 0.0
    frozen_at: str | None = None  # ISO-8601 with offset

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict | None) -> ClockState:
        return cls(**data) if data else cls()


class Clock:
    def __init__(self, tz: ZoneInfo, state: ClockState | None = None, wall=None):
        self.tz = tz
        self.state = state or ClockState()
        self._wall = wall or (lambda: datetime.now(timezone.utc))

    def now(self) -> datetime:
        if self.state.mode == "frozen" and self.state.frozen_at:
            return datetime.fromisoformat(self.state.frozen_at).astimezone(self.tz)
        now = self._wall().astimezone(self.tz)
        if self.state.mode == "offset":
            now += timedelta(seconds=self.state.offset_s)
        return now

    def jump_to(self, when: datetime) -> tuple[datetime, datetime]:
        """Move the clock to `when` and keep it running from there. Returns (before, after)."""
        before = self.now()
        when = _aware(when, self.tz)
        if self.state.mode == "frozen":
            self.state = ClockState(mode="frozen", frozen_at=when.isoformat())
        else:
            offset = (when - self._wall()).total_seconds()
            self.state = ClockState(mode="offset", offset_s=offset)
        return before, self.now()

    def advance(self, delta: timedelta) -> tuple[datetime, datetime]:
        return self.jump_to(self.now() + delta)

    def freeze(self, at: datetime | None = None) -> datetime:
        at = _aware(at, self.tz) if at else self.now()
        self.state = ClockState(mode="frozen", frozen_at=at.isoformat())
        return at

    def unfreeze(self) -> datetime:
        """Keep the current demo time but let it flow again."""
        at = self.now()
        self.state = ClockState(mode="offset", offset_s=(at - self._wall()).total_seconds())
        return self.now()

    def reset(self) -> datetime:
        self.state = ClockState()
        return self.now()

    def describe(self) -> str:
        label = {"real": "real time", "offset": "fast-forwarded", "frozen": "frozen"}[self.state.mode]
        return f"{self.now():%a %d %b %Y %H:%M:%S %Z} ({label})"


def _aware(when: datetime, tz: ZoneInfo) -> datetime:
    return when.replace(tzinfo=tz) if when.tzinfo is None else when


def parse_when(text: str, clock: Clock) -> datetime:
    """Accept 'HH:MM' (today, demo time), an ISO date-time, or '+90m' / '+2h' / '+1d'."""
    text = text.strip()
    if text.startswith("+"):
        unit = text[-1]
        amount = float(text[1:-1])
        delta = {"m": timedelta(minutes=amount), "h": timedelta(hours=amount), "d": timedelta(days=amount)}[unit]
        return clock.now() + delta
    if len(text) <= 5 and ":" in text:
        hour, minute = (int(x) for x in text.split(":"))
        return clock.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return _aware(datetime.fromisoformat(text), clock.tz)


class ClockStore:
    """Loads and saves the shared clock state in the `settings` table."""

    def __init__(self, db):
        self.db = db

    async def load(self, tz: ZoneInfo) -> Clock:
        value = await self.db.get_setting(SETTINGS_KEY)
        return Clock(tz, ClockState.from_json(value))

    async def save(self, clock: Clock) -> None:
        await self.db.set_setting(SETTINGS_KEY, clock.state.to_json())
