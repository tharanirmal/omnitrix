"""The action gate: code sets the tier, the judge can only raise it or block, the owner approves the rest."""
import math

import pytest

from engram.act import Gate, Tool
from engram.judge import Judge

pytestmark = pytest.mark.db


class Intent:
    """P(yes) for the intent question, chosen by a phrase in the proposed action."""

    model = "intent-scripted"

    def __init__(self, table: dict[str, float]):
        self.table = table

    def score(self, system, user, keys):
        p = next((v for k, v in self.table.items() if k in user), 0.99)
        return {"yes": math.log(p), "no": math.log(1 - p)}


def tools():
    noop = lambda **kw: "ok"  # noqa: E731
    return {"search": Tool("email.search", "read", noop), "task": Tool("tasks.create", "internal", noop),
            "send": Tool("email.send", "external", noop), "delete": Tool("email.delete", "destructive", noop)}


def test_gate_tiers_blocks_and_approvals(db_url):
    t = tools()
    judge_scores = Intent({"eve@": 0.01, "maybe@": 0.6, "doubt@": 0.3})    # eve: clearly wrong; the rest unsure
    with Judge(db_url, judge_scores) as judge:
        strict = Gate(judge)                                         # nobody approves
        yes_man = Gate(judge, approve=lambda request, tool, args, verdict: True)
        ask = "Email Bob the Q3 numbers"
        assert strict.check(ask, t["search"], {"q": "Q3"}, "s1").reason == "read-only"
        assert strict.check(ask, t["task"], {"title": "Q3"}, "s2").reason == "auto"
        assert strict.check(ask, t["send"], {"to": "bob@x.com"}, "s3").reason == "awaiting approval"
        assert yes_man.check(ask, t["send"], {"to": "bob@x.com"}, "s3").reason == "approved"
        blocked = yes_man.check(ask, t["send"], {"to": "eve@x.com"}, "s4")
        assert not blocked.allowed and blocked.reason.startswith("blocked")      # even an eager approver can't
        unsure = strict.check(ask, t["task"], {"assignee": "maybe@x.com"}, "s5")
        assert unsure.reason == "awaiting approval"                              # doubt goes to the owner
        autonomous = Gate(judge, auto_tier=3)
        assert autonomous.check(ask, t["send"], {"to": "bob@x.com"}, "s3").reason == "auto"
        assert autonomous.check(ask, t["task"], {"assignee": "maybe@x.com"}, "s5").reason == "awaiting approval"
        leaning_no = yes_man.check(ask, t["task"], {"assignee": "doubt@x.com"}, "s7")
        assert leaning_no.reason == "approved" and leaning_no.verdict.value == "no"   # only a sure no blocks
    ungated = Gate(None, auto_tier=3)
    assert ungated.check(ask, t["delete"], {"id": 1}, "s6").allowed           # no judge: code tier only
