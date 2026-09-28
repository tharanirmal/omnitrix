import numpy as np

from engram import calibrate as cal


def test_fit_temperature_recovers_overconfidence():
    rng = np.random.default_rng(0)
    true = rng.normal(size=(4000, 2))
    y = np.array([rng.choice(2, p=p) for p in cal.softmax(true)])
    t = cal.fit_temperature(true * 3.0, y)            # logits inflated 3x: an overconfident model
    assert 2.6 < t < 3.4


def test_wilson_lower_bound():
    assert cal.wilson_lower(0, 0) == 0.0
    assert 0.80 < cal.wilson_lower(95, 100) < 0.95 < cal.wilson_lower(990, 1000)


def test_noul_band_settles_only_where_precision_holds():
    p = np.array([0.99] * 100 + [0.6] * 20 + [0.01] * 100)
    is_yes = np.array([True] * 100 + [True] * 10 + [False] * 10 + [False] * 100)
    lo, hi = cal.noul_band(p, is_yes, target=0.9)
    assert hi == 0.99 and lo == 0.01                    # the mixed 0.6 group stays in the uncertain band


def test_noul_band_settles_nothing_when_target_unreachable():
    p = np.linspace(0, 1, 50)
    lo, hi = cal.noul_band(p, np.arange(50) % 2 == 0, target=0.95)
    assert lo < 0 and hi > 1


def test_top_band():
    p = np.array([0.95] * 50 + [0.5] * 50)
    correct = np.array([True] * 50 + [True, False] * 25)
    assert cal.top_band(p, correct, target=0.9) == 0.95


def test_auroc_and_ece():
    s = np.array([0.9, 0.8, 0.3, 0.2])
    assert cal.auroc(s, np.array([True, True, False, False])) == 1.0
    assert cal.auroc(s, np.array([False, False, True, True])) == 0.0
    assert cal.ece(np.array([0.8] * 10), np.array([True] * 8 + [False] * 2)) < 1e-9


def test_report_for_yes_no():
    probs = np.array([[0.9, 0.1], [0.2, 0.8], [0.7, 0.3]])
    r = cal.report(probs, np.array([0, 1, 1]))
    assert r["n"] == 3 and r["accuracy"] == round(2 / 3, 4) and 0 <= r["brier"] <= 1 and r["auroc"] == 1.0
