"""evaluate(): the fit/test split respects conversations, calibration is stored, the cascade adds up."""
import hashlib
import math

import pytest

from engram.db import connect
from engram.evaluate import evaluate
from engram.judge import noul
from engram.labels import Example

pytestmark = pytest.mark.db


class Noisy:
    """Right on a fixed `accuracy` share of examples (chosen by hash), always with the same confidence."""

    def __init__(self, model: str, accuracy: float, confidence: float, truth: dict[str, str]):
        self.model, self.accuracy, self.confidence, self.truth = model, accuracy, confidence, truth

    def score(self, system, user, keys):
        case = next(k for k in self.truth if k in user)
        right = int(hashlib.sha256(f"{self.model}{case}".encode()).hexdigest(), 16) % 1000 < self.accuracy * 1000
        says_yes = (self.truth[case] == "yes") == right
        p_yes = self.confidence if says_yes else 1 - self.confidence
        return {"yes": math.log(p_yes), "no": math.log(1 - p_yes)}


def test_evaluate_reports_and_stores_calibration(db_url):
    q = noul("demo", "Is it yes?")
    examples = [Example(q, f"case {i}", f"item:{i}", "yes" if i % 2 else "no", "benchmark", f"thread:{i // 3}")
                for i in range(480)]
    truth = {f"case {i}\n": e.label for i, e in enumerate(examples)}
    small, big = Noisy("small", 0.7, 0.9, truth), Noisy("big", 0.995, 0.99, truth)
    report = evaluate(db_url, examples, [("S1", small), ("S2", big)])

    assert report["n"] == 480 and 150 < report["n_test"] < 330
    s, b = report["models"]["small"], report["models"]["big"]
    assert 0.6 < s["calibrated"]["accuracy"] < 0.8 and s["temperature"] > 1        # overconfident: softened
    assert s["settled_rate"] < 0.1 < 0.8 < b["settled_rate"]                       # only the strong model settles
    c = report["cascade"]
    assert math.isclose(c["settled_by_s1"] + c["sent_to_s2"], 1.0, abs_tol=1e-3)
    assert c["left_for_human"] < 0.2 and c["accuracy_when_settled"] > 0.95
    with connect(db_url) as conn:
        stored = {r["model"] for r in conn.execute("SELECT model FROM calibration WHERE question = 'demo'")}
        labelled = conn.execute("SELECT count(*) AS n FROM labels WHERE question = 'demo'").fetchone()["n"]
    assert stored == {"small", "big"} and labelled == 480


def test_escalation_measurements_survive_re_evaluation(db_url):
    from engram.judge import load_no_escalation

    q = noul("demo2", "Is it yes?")
    examples = [Example(q, f"case {i}", f"item:{i}", "yes" if i % 2 else "no", "benchmark", f"thread:{i // 3}")
                for i in range(240)]
    truth = {f"case {i}\n": e.label for i, e in enumerate(examples)}
    big = Noisy("big2", 0.6, 0.9, truth)                                        # worse than both small judges
    evaluate(db_url, examples, [("S1", Noisy("small-a", 0.9, 0.7, truth)), ("S2", big)])
    evaluate(db_url, examples, [("S1", Noisy("small-b", 0.9, 0.7, truth)), ("S2", big)])   # a new adapter, say
    evaluate(db_url, examples, [("S1", Noisy("small-b", 0.9, 0.7, truth))])                 # S1 alone
    with connect(db_url) as conn:
        skip = load_no_escalation(conn)
    assert {("demo2", "small-a", "big2"), ("demo2", "small-b", "big2")} <= skip
