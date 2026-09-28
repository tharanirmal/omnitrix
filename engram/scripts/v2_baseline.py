"""Adapter v2, before training: how the current judge (v1, 4-bit) and the 14B do on the new decisions, measured
against the derived labels (and the team's labels where they exist). Read-only: the models are called directly, so
nothing lands in the ledger or the calibration table (fitting a live calibration on unchecked labels would change
how the running brain settles these questions). Writes data/results/v2-baseline.json.

    uv run python scripts/v2_baseline.py --n 150
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time

import numpy as np

from engram import derive
from engram.config import Settings
from engram.db import connect
from engram.finetune import split_of
from engram.judge import SYSTEM, make_scorer
from engram.labels import Example
from engram.memory import REMEMBER, reading_text


def auroc(p: np.ndarray, y: np.ndarray) -> float | None:
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return None
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum())
                 / (len(pos) * len(neg)))


def gold(conn, s: Settings) -> list[Example]:
    """The 90 emails hand-labelled for `remember` when the gate was designed (LR §10.7): never trained on, so a
    clean check of the gate beside the checked test split."""
    d = json.loads((s.data_dir / "results" / "remember-gold.json").read_text())
    labels = {int(i): v for part in ("dev", "test") for i, v in d[part].items()}
    rows = conn.execute("SELECT id, subject, from_addr, body, quoted FROM items WHERE id = ANY(%s)",
                        (list(labels),)).fetchall()
    return [Example(REMEMBER, reading_text(r), f"item:{r['id']}", labels[r["id"]], "gold", f"item:{r['id']}")
            for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="examples per decision (balanced where the labels allow)")
    ap.add_argument("--models", default="", help="comma-separated scorer specs (default: the judge and the 14B)")
    ap.add_argument("--test-only", action="store_true",
                    help="after training: only checked examples in the held-out test split, all of them (no sampling),"
                         " plus the 90 hand-labelled remember items as their own set")
    ap.add_argument("--old", action="store_true", help="with --test-only: also round 1's four decisions")
    ap.add_argument("--out", default="v2-baseline.json", help="file name under data/results")
    args = ap.parse_args()
    s = Settings()
    specs = args.models.split(",") if args.models else [s.judge_model or s.s1_model, s.s2_model]
    rng = random.Random(0)
    out: dict = {"n_per_decision": args.n, "decisions": {},
                 "labels": "checked (team or assistant), test split only" if args.test_only
                 else "human where checked, else derived"}
    with connect(s.database_url) as conn:
        sets = {}
        for name in ("remember", "meeting_request", "fulfilled", "contradicts", "todo"):
            ex = [e for e in derive.examples(conn, name, human_only=args.test_only) if e.label in ("yes", "no")]
            if args.test_only:
                sets[name] = [e for e in ex if split_of(e.group) == "test"]
                continue
            yes = [e for e in ex if e.label == "yes"]
            no = [e for e in ex if e.label == "no"]
            k = min(args.n // 2, len(yes), len(no))
            sets[name] = rng.sample(yes, k) + rng.sample(no, k)
        if args.test_only:
            sets["remember (gold 90)"] = gold(conn, s)
    if args.test_only and args.old:                      # round 1's decisions, on v1's exact test split
        from engram.cli import _examples

        for name in ("supported", "relevant", "replied", "filed"):
            sets[name] = [e for e in _examples(name, 1500, 0) if split_of(e.group) == "test"]
    for spec in specs:
        scorer = make_scorer(spec, s.ollama_url)
        for name, ex in sets.items():
            if not ex:
                out["decisions"].setdefault(name, {})["note"] = "no labelled examples yet"
                continue
            t0, probs = time.monotonic(), []
            for e in ex:
                try:
                    lp = scorer.score(SYSTEM, e.question.render(e.state), e.question.keys)
                    w = [math.exp(lp[k]) for k in e.question.keys]
                    probs.append([x / sum(w) for x in w])
                except Exception:                                  # an invalid answer: no information
                    probs.append([1 / len(e.question.keys)] * len(e.question.keys))
            right = [e.question.labels[int(np.argmax(q))] == e.label for e, q in zip(ex, probs, strict=True)]
            d = out["decisions"].setdefault(name, {"n": len(ex), "human": sum(e.source == "human" for e in ex)})
            d[spec] = {"accuracy": round(float(np.mean(right)), 3),
                       "ms_per_item": round((time.monotonic() - t0) * 1000 / len(ex))}
            if ex[0].question.kind == "noul":
                p_arr, y = np.array([q[0] for q in probs]), np.array([e.label == "yes" for e in ex], dtype=int)
                d[spec] |= {"auroc": None if (a := auroc(p_arr, y)) is None else round(a, 3),
                            "mean_p_yes": round(float(p_arr.mean()), 3)}
            print(name, spec, d[spec], flush=True)
    path = s.data_dir / "results" / args.out
    path.write_text(json.dumps(out, indent=2))
    print(f"written {path}")


if __name__ == "__main__":
    main()
