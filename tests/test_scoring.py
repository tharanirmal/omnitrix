from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from omnitrix.planner.scoring import ScoreInput, score_task

TZ = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 8, 9, 0, tzinfo=TZ)


def test_worked_example_from_the_design_scores_87():
    p = score_task(ScoreInput(now=NOW, due_at=NOW + timedelta(days=1), requester_name="Mehta",
                              requester_importance=3, money_inr=20 * 100_000, times_missed=1))
    assert p.score == 87
    assert p.reasons == [
        "deadline in 1 day (+35)",
        "requested by a key contact Mehta (+30)",
        "linked to ₹20 L deal (+15)",
        "missed once already (+7)",
    ]


def test_overdue_hard_deadline_ranks_highest_and_is_clamped():
    p = score_task(ScoreInput(now=NOW, due_at=NOW - timedelta(hours=2), hard_deadline=True,
                              requester_importance=3, money_inr=5_00_00_000, times_missed=5))
    assert p.score == 100
    assert p.reasons[0] == "overdue by 2 h (+40)"
    assert "missed 5 times already (+21)" in p.reasons


def test_no_deadline_and_no_context_scores_zero():
    p = score_task(ScoreInput(now=NOW))
    assert p.score == 0 and p.reasons == []


def test_closer_deadline_scores_higher():
    def s(delta):
        return score_task(ScoreInput(now=NOW, due_at=NOW + delta)).score
    assert s(timedelta(hours=2)) > s(timedelta(hours=20)) > s(timedelta(days=2)) > s(timedelta(days=6)) \
        > s(timedelta(days=30))


def test_small_amounts_are_worded_in_rupees():
    p = score_task(ScoreInput(now=NOW, money_inr=45_000))
    assert p.reasons == ["involves ₹45,000 (+5)"]
