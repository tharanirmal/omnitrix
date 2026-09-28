"""Calibration maths for the judge: temperature fitting, the uncertain band, and measurement (LR §1.3, §8).
Pure numpy; no database, no models."""
from __future__ import annotations

import math

import numpy as np

Z95 = 1.645                  # one-sided 95%


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = logits / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    """Temperature minimising the negative log-likelihood of the true labels (golden-section search on log T).
    logits: (n, k) raw log-probabilities per label; y: (n,) index of the true label."""
    rows = np.arange(len(y))

    def nll(log_t: float) -> float:
        return float(-np.log(softmax(logits, math.exp(log_t))[rows, y] + 1e-12).mean())

    lo, hi, g = math.log(0.05), math.log(50.0), (math.sqrt(5) - 1) / 2
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    fa, fb = nll(a), nll(b)
    for _ in range(60):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - g * (hi - lo)
            fa = nll(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + g * (hi - lo)
            fb = nll(b)
    return math.exp((lo + hi) / 2)


def wilson_lower(successes: int, n: int, z: float = Z95) -> float:
    """One-sided lower confidence bound on a proportion (Wilson score interval)."""
    if n == 0:
        return 0.0
    p = successes / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / (1 + z * z / n)


def noul_band(p_yes: np.ndarray, is_yes: np.ndarray, target: float = 0.95) -> tuple[float, float]:
    """(tau_lo, tau_hi) for a yes/no decision: the widest regions 'P(yes) >= tau_hi -> yes' and
    'P(yes) <= tau_lo -> no' whose precision keeps a 95% lower bound of at least `target` (SUPG-style, LR §1.3).
    Everything in between escalates. A side that cannot reach the target settles nothing."""
    tau_hi, tau_lo = 1.01, -0.01
    for t in np.unique(p_yes):
        sel = p_yes >= t
        if wilson_lower(int(is_yes[sel].sum()), int(sel.sum())) >= target:
            tau_hi = min(tau_hi, float(t))
        sel = p_yes <= t
        if wilson_lower(int((~is_yes[sel]).sum()), int(sel.sum())) >= target:
            tau_lo = max(tau_lo, float(t))
    if tau_lo >= tau_hi:                    # regions overlap only on tiny samples: split the difference
        tau_lo = tau_hi = (tau_lo + tau_hi) / 2
    return tau_lo, tau_hi


def top_band(p_top: np.ndarray, correct: np.ndarray, target: float = 0.95) -> float:
    """tau_hi for a choice: the lowest top probability above which accuracy keeps a 95% lower bound >= target."""
    tau = 1.01
    for t in np.unique(p_top):
        sel = p_top >= t
        if wilson_lower(int(correct[sel].sum()), int(sel.sum())) >= target:
            tau = min(tau, float(t))
    return tau


def auroc(scores: np.ndarray, positive: np.ndarray) -> float:
    """Probability that a random positive outscores a random negative (ties count half)."""
    pos, neg = scores[positive], scores[~positive]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def ece(p_top: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error over equal-width confidence bins."""
    idx = np.minimum((p_top * bins).astype(int), bins - 1)
    return float(sum(abs(correct[idx == b].mean() - p_top[idx == b].mean()) * (idx == b).mean()
                     for b in range(bins) if (idx == b).any()))


def report(probs: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Accuracy, ECE, and for two-label decisions (label 0 = 'yes') Brier score and AUROC."""
    pred, top = probs.argmax(axis=1), probs.max(axis=1)
    correct = pred == y
    out = {"n": len(y), "accuracy": float(correct.mean()), "ece": ece(top, correct)}
    if probs.shape[1] == 2:
        is_yes = y == 0
        out["brier"] = float(((probs[:, 0] - is_yes) ** 2).mean())
        out["auroc"] = auroc(probs[:, 0], is_yes)
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in out.items()}
