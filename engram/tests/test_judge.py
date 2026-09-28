"""The judge's cascade, cache and ledger, with scripted scorers instead of models."""
import math

import pytest

from engram.db import connect
from engram.judge import Judge, ScoringError, choice, noul, score, verify_ledger


class Scripted:
    """Answers P(first key) = p for every prompt; counts calls."""

    def __init__(self, model: str, p: float | None):
        self.model, self.p, self.calls = model, p, 0

    def score(self, system, user, keys):
        self.calls += 1
        if self.p is None:
            raise ScoringError("no valid key")
        rest = (1 - self.p) / (len(keys) - 1)
        return {k: math.log(self.p if i == 0 else rest) for i, k in enumerate(keys)}


def test_question_rendering_and_validation():
    q = choice("folder", "Which folder?", {"projects": "research projects", "hr": ""})
    text = q.render("hello")
    assert q.keys == ("A", "B") and "A) projects: research projects" in text and "B) hr" in text
    assert noul("x", "Is it?").render("m").endswith("Answer with one word: yes or no.")
    assert score("prio", "How urgent?", ["low", "mid", "high"]).labels == ("low", "mid", "high")
    with pytest.raises(ValueError):
        choice("x", "?", ["only one"])


@pytest.mark.db
def test_cascade_cache_and_ledger(db_url):
    q = noul("worth_remembering", "Is this worth remembering?")
    memo = "Board meeting moved to Friday."
    sure, unsure, big = Scripted("s1", 0.97), Scripted("s1b", 0.6), Scripted("s2", 0.99)

    with Judge(db_url, sure, big) as judge:
        v = judge.ask(q, memo, "item:1")
    assert (v.value, v.tier, v.settled, big.calls) == ("yes", "S1", True, 0)          # S1 sure: no S2 call

    with Judge(db_url, unsure, big) as judge:
        v = judge.ask(q, memo, "item:1")
    assert (v.tier, v.settled, [a.tier for a in v.answers]) == ("S2", True, ["S1", "S2"])

    with Judge(db_url, unsure, Scripted("s2b", 0.5)) as judge:
        assert not judge.ask(q, "Lunch?", "item:2").settled                            # both unsure: a human's call

    with Judge(db_url, sure, big) as judge:
        again = judge.ask(q, memo, "item:1")
    assert sure.calls == 1 and again.answers[0].latency_ms == 0                        # served from the ledger

    with Judge(db_url, Scripted("bad", None), big) as judge:
        broken = judge.ask(q, "Anything", "item:3")
    assert broken.answers[0].value == "" and broken.tier == "S2"                       # invalid output escalates

    with connect(db_url) as conn:
        assert verify_ledger(conn) is None
        conn.execute("UPDATE judgements SET value = 'no' WHERE id = (SELECT min(id) FROM judgements)")
        assert verify_ledger(conn) is not None                                         # tampering is detected
        conn.rollback()


@pytest.mark.db
def test_fitted_calibration_moves_the_band(db_url):
    with connect(db_url) as conn:
        conn.execute("INSERT INTO calibration (question, model, temperature, tau_lo, tau_hi) "
                     "VALUES ('replied', 'm1', 1.0, 0.05, 0.999)")
    with Judge(db_url, Scripted("m1", 0.97)) as judge:
        v = judge.ask(noul("replied", "Would the owner reply?"), "Please call me.", "item:9")
    assert v.value == "yes" and not v.settled               # 0.97 is below this model's fitted tau_hi


class FakeHTTP:
    def __init__(self, top):
        self.top = top

    def post(self, path, json):
        top = self.top
        return type("R", (), {"raise_for_status": lambda self: None,
                              "json": lambda self: {"logprobs": [{"top_logprobs": top}]}})()


def test_ollama_scorer_matches_keys_in_any_casing_and_floors_the_rest():
    from engram.judge import OllamaScorer

    s = OllamaScorer("http://unused", "m")
    s._http = FakeHTTP([{"token": "Yes", "logprob": -0.1}, {"token": " yes", "logprob": -2.5},
                        {"token": "No", "logprob": -3.0}, {"token": "Maybe", "logprob": -4.0}])
    lp = s.score("sys", "user", ("yes", "no"))
    assert lp["yes"] == pytest.approx(math.log(math.exp(-0.1) + math.exp(-2.5))) and lp["no"] == -3.0
    letters = s.score("sys", "user", ("A", "B", "Yes"))
    assert letters["A"] == letters["B"] == -6.0                             # absent: below everything in the top 20
    s._http = FakeHTTP([{"token": "Maybe", "logprob": -0.1}])
    with pytest.raises(ScoringError):
        s.score("sys", "user", ("yes", "no"))


@pytest.mark.db
def test_negative_zero_survives_the_ledger_round_trip(db_url):
    class NegZero:
        model = "negzero"

        def score(self, system, user, keys):
            return {"yes": -0.0, "no": -30.0}                               # jsonb would store -0.0 as 0.0

    with Judge(db_url, NegZero()) as judge:
        judge.ask(noul("nz", "Is it?"), "material", "s")
    with connect(db_url) as conn:
        assert verify_ledger(conn) is None


@pytest.mark.db
def test_no_escalation_where_s2_is_measured_no_better(db_url):
    with connect(db_url) as conn:
        conn.execute("INSERT INTO calibration (question, model, temperature, tau_lo, tau_hi, metrics) VALUES "
                     "('personal', 's2', 1, 0.1, 0.9, %s)",
                     ('{"escalated_from": {"s1": {"n": 50, "s1_accuracy": 0.6, "s2_accuracy": 0.55}}}',))
    small, big = Scripted("s1", 0.6), Scripted("s2", 0.99)            # S1 unsure; S2 confident but worse here
    with Judge(db_url, small, big) as judge:
        v = judge.ask(noul("personal", "Will they reply?"), "an email", "item:1")
        w = judge.ask(noul("other", "Is it?"), "an email", "item:1")   # no measurement: escalates as usual
    assert (v.tier, v.settled, big.calls) == ("S1", False, 1) and w.tier == "S2"
