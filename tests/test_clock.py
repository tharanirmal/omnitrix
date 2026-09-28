from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from omnitrix.core.clock import Clock, ClockState, parse_when

TZ = ZoneInfo("Asia/Kolkata")


class FakeWall:
    def __init__(self, at: datetime):
        self.at = at

    def __call__(self) -> datetime:
        return self.at


def test_real_mode_follows_the_wall_clock_in_local_time():
    wall = FakeWall(datetime(2026, 10, 8, 3, 30, tzinfo=timezone.utc))
    assert Clock(TZ, wall=wall).now() == datetime(2026, 10, 8, 9, 0, tzinfo=TZ)


def test_jump_keeps_time_flowing():
    wall = FakeWall(datetime(2026, 10, 8, 3, 30, tzinfo=timezone.utc))
    clock = Clock(TZ, wall=wall)
    clock.jump_to(datetime(2026, 10, 8, 14, 0, tzinfo=TZ))
    assert clock.now() == datetime(2026, 10, 8, 14, 0, tzinfo=TZ)
    wall.at += timedelta(minutes=5)
    assert clock.now() == datetime(2026, 10, 8, 14, 5, tzinfo=TZ)
    assert clock.state.mode == "offset"


def test_freeze_stops_time_and_jump_while_frozen_stays_frozen(clock):
    t0 = clock.now()
    assert clock.now() == t0
    clock.advance(timedelta(hours=2, minutes=10))
    assert clock.now() == datetime(2026, 10, 8, 11, 5, tzinfo=TZ)
    assert clock.state.mode == "frozen"


def test_unfreeze_resumes_from_the_frozen_moment():
    wall = FakeWall(datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc))
    clock = Clock(TZ, wall=wall)
    clock.freeze(datetime(2026, 10, 8, 8, 55, tzinfo=TZ))
    clock.unfreeze()
    wall.at += timedelta(minutes=1)
    assert clock.now() == datetime(2026, 10, 8, 8, 56, tzinfo=TZ)


def test_state_round_trips_through_json(clock):
    restored = Clock(TZ, ClockState.from_json(clock.state.to_json()))
    assert restored.now() == clock.now()


def test_parse_when_formats(clock):
    assert parse_when("11:05", clock) == datetime(2026, 10, 8, 11, 5, tzinfo=TZ)
    assert parse_when("+90m", clock) == datetime(2026, 10, 8, 10, 25, tzinfo=TZ)
    assert parse_when("+1d", clock) == datetime(2026, 10, 9, 8, 55, tzinfo=TZ)
    assert parse_when("2026-10-09T20:00", clock) == datetime(2026, 10, 9, 20, 0, tzinfo=TZ)
