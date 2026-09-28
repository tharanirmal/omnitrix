"""Measure judges on labelled examples and fit their calibration (LR §8). For each model: accuracy, ECE, Brier and
AUROC before and after temperature scaling, the uncertain band for a target precision, and how often it settles;
then the S1 -> S2 cascade. Calibration is fitted on one half and measured on the other; the stored calibration is
refitted on all of it."""
from __future__ import annotations

import contextlib
import hashlib
import json
import random
import time
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import psycopg

from . import agent as ag
from . import calibrate as cal
from .act import TIER, Gate, Tool
from .ask import ask
from .finetune import split_of
from .index import Embed, fuse, ranked
from .judge import Judge, Scorer, noul
from .labels import Example, answerable, groups
from .llm import Ollama
from .sources import workbench as wb
from .sources.enronqa import QA

KS = (1, 5, 10)
# the owner's setting -> (ask the intent judge, highest tier run without the owner); None: no gate at all
POLICIES: dict[str, tuple[bool, int] | None] = {
    "no gate": None,
    "owner approves external & destructive": (False, TIER["internal"]),
    "judge + owner (default autonomy)": (True, TIER["internal"]),
    "judge, full autonomy": (True, TIER["destructive"]),
}


def evaluate(url: str, examples: Sequence[Example], scorers: Sequence[tuple[str, Scorer]],
             target: float = 0.95) -> dict:
    kind, name = examples[0].question.kind, examples[0].question.name
    y = np.array([e.question.labels.index(e.label) for e in examples])
    # fit on one half of the conversations, measure on the other: a thread never straddles the split
    test = np.array([int(hashlib.sha256(e.group.encode()).hexdigest(), 16) % 2 == 1 for e in examples])
    report: dict = {"decision": name, "n": len(examples), "n_test": int(test.sum()), "models": {}}
    final: dict[str, tuple[np.ndarray, np.ndarray]] = {}     # tier -> (calibrated probs, settled)

    with Judge(url, scorers[0][1]) as judge:
        with judge.conn.cursor() as cur:
            cur.executemany("INSERT INTO labels (question, subject, value, source) VALUES (%s, %s, %s, %s) "
                            "ON CONFLICT DO NOTHING", [(name, e.subject, e.label, e.source) for e in examples])
        for tier, scorer in scorers:
            answers = [judge.answer(tier, scorer, e.question, e.state, e.subject) for e in examples]
            valid = np.array([bool(a.logprobs) for a in answers])
            logits = np.array([[a.logprobs.get(label, -30.0) for label in e.question.labels]
                               for a, e in zip(answers, examples, strict=True)])

            fit, ev = valid & ~test, valid & test
            t_fit = cal.fit_temperature(logits[fit], y[fit])
            lo, hi = _band(kind, cal.softmax(logits[fit], t_fit), y[fit], target)
            probs = cal.softmax(logits, t_fit)
            settled = _settled(kind, probs, lo, hi) & valid
            fresh = [a.latency_ms for a in answers if a.latency_ms > 0]
            m = {"raw": cal.report(cal.softmax(logits[ev]), y[ev]), "calibrated": cal.report(probs[ev], y[ev]),
                 "temperature": round(t_fit, 3), "band": [round(lo, 3), round(hi, 3)],
                 "settled_rate": round(float(settled[ev].mean()), 3),
                 "settled_accuracy": _acc(probs, y, settled & test),
                 "invalid_rate": round(float(1 - valid.mean()), 3),
                 "median_latency_ms": round(float(np.median(fresh)), 1) if fresh else None}
            report["models"][scorer.model] = m
            final[tier] = (probs, settled)

            t_all = cal.fit_temperature(logits[valid], y[valid])           # stored calibration: fitted on all
            lo_all, hi_all = _band(kind, cal.softmax(logits[valid], t_all), y[valid], target)
            judge.conn.execute(
                "INSERT INTO calibration (question, model, temperature, tau_lo, tau_hi, metrics) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (question, model) DO UPDATE SET "
                "temperature = EXCLUDED.temperature, tau_lo = EXCLUDED.tau_lo, tau_hi = EXCLUDED.tau_hi, "
                "metrics = calibration.metrics || EXCLUDED.metrics, fitted_at = now()",   # keeps escalated_from
                (name, scorer.model, t_all, lo_all, hi_all, json.dumps(m)))

    if len(final) == 2:
        (p1, s1), (p2, s2) = final["S1"], final["S2"]
        pred = np.where(s1, p1.argmax(1), p2.argmax(1))
        n, up = test.sum(), ~s1 & test                      # up: what S1 escalates
        # S2 only ever sees what S1 escalates — the hard cases — so it is judged on those alone (a band fitted on
        # every example overstates how sure it can be there)
        escalated = {"n": int(up.sum()), "s1_accuracy": _acc(p1, y, up), "s2_accuracy": _acc(p2, y, up),
                     "s2_settled_accuracy": _acc(p2, y, up & s2)}
        report["cascade"] = {"forced_accuracy": round(float((pred == y)[test].mean()), 3),   # even unsettled
                             "settled_by_s1": round(float((s1 & test).sum() / n), 3),
                             "sent_to_s2": round(float(up.sum() / n), 3),
                             "left_for_human": round(float((up & ~s2).sum() / n), 3),
                             "accuracy_when_settled": _acc(np.where(s1[:, None], p1, p2), y, (s1 | s2) & test),
                             "escalated": escalated}
        with psycopg.connect(url, autocommit=True) as conn:        # what Judge reads to route this decision;
            conn.execute("UPDATE calibration SET metrics = jsonb_set(metrics, '{escalated_from}', "   # one entry per
                         "coalesce(metrics -> 'escalated_from', '{}') || %s) "                          # S1 model
                         "WHERE question = %s AND model = %s",
                         (json.dumps({scorers[0][1].model: escalated}), name, scorers[1][1].model))
    return report


def retrieval(conn: psycopg.Connection, embed: Embed, qas: Sequence[QA], n: int, rng: random.Random) -> dict:
    """Recall@k and MRR of each search and fusion variant on benchmark questions: the gold email must be found.
    Each question is embedded and searched once; every variant is scored from the same candidate lists."""
    pool, ids = answerable(conn, qas)
    picked = rng.sample(pool, min(n, len(pool)))
    variants = {"keywords": lambda r: fuse({"keywords": r["keywords"]}),
                "meaning": lambda r: fuse({"meaning": r["meaning"]}),
                "hybrid (standard rrf)": lambda r: fuse(r, 60, {"keywords": 1.0, "meaning": 1.0}),
                "hybrid (engram)": lambda r: fuse(r)}
    ranks: dict[str, list[int | None]] = {v: [] for v in variants}
    for q in picked:
        lists = ranked(conn, q.question, embed([q.question])[0])
        for name, variant in variants.items():
            items = [item for _, item, _, _ in variant(lists)]
            ranks[name].append(items.index(ids[q.ref]) + 1 if ids[q.ref] in items else None)
    return {"questions": len(picked), "variants": {
        name: {**{f"recall@{k}": round(sum(1 for x in r if x and x <= k) / len(r), 3) for k in KS},
               "mrr": round(sum(1 / x for x in r if x) / len(r), 3)} for name, r in ranks.items()}}


MATCHES = ("Does the response give the reference answer? It may phrase it differently or add correct detail. Answer "
           "no if it contradicts the reference, misses a fact the question asks for, or says it does not know.")


def qa(conn: psycopg.Connection, judge: Judge, grader: Judge, llm: Ollama, model: str, embed: Embed,
       qas: Sequence[QA], n: int, rng: random.Random, draft: str | None = None) -> tuple[dict, list[dict]]:
    """Answer EnronQA questions with `ask`, only those whose email lies in conversations the judge was never trained
    on (the fine-tuning test split). The grader (the large model, one token) compares each answer with the
    reference. Reported: how often the gold email is retrieved, kept and cited; accuracy; and whether the judge's
    support check tells right answers from wrong ones."""
    pool, ids = answerable(conn, qas)
    group = groups(conn, [ids[q.ref] for q in pool])
    pool = [q for q in pool if split_of(group[ids[q.ref]]) == "test"]
    rows, out = [], []
    for q in rng.sample(pool, min(n, len(pool))):
        t0 = time.perf_counter()
        r = ask(conn, judge, llm, model, embed, q.question, draft=draft)
        seconds = time.perf_counter() - t0
        grade = grader.ask(noul("matches", MATCHES), f"Question: {q.question}\nReference answer: {q.gold}\n"
                                                     f"Response: {r.answer}", f"qa:{q.qid}")
        gold, s = ids[q.ref], r.support
        rows.append((gold in r.considered, gold in r.kept, gold in r.cites, bool(r.cites), grade.value == "yes",
                     s.probs["yes"] if s else 0.0, bool(s and s.settled and s.value == "yes"),
                     bool(s and s.settled and s.value == "no")))
        out.append({"qid": q.qid, "question": q.question, "reference": q.gold, "answer": r.answer,
                    "cites": list(r.cites), "gold_item": gold, "correct": grade.value == "yes",
                    "seconds": round(seconds, 2), "answered_by": r.answered_by,
                    "support": None if s is None else {"p_yes": round(s.probs["yes"], 3), "settled": s.settled,
                                                       "tier": s.tier}})
    a = np.array(rows, dtype=float).reshape(-1, 8)
    retrieved, kept, cited, answered, correct, p_support, sure, refuted = a.T
    sure, refuted, correct = sure.astype(bool), refuted.astype(bool), correct.astype(bool)
    secs = sorted(o["seconds"] for o in out)
    return {"questions": len(rows), "seconds_p50": secs[len(secs) // 2] if secs else None,
            "seconds_p90": secs[int(len(secs) * 0.9)] if secs else None,
            "answered_by": {m: sum(o["answered_by"] == m for o in out) for m in {o["answered_by"] for o in out}},
            "gold_retrieved": _mean(retrieved), "gold_kept": _mean(kept),
            "gold_cited": _mean(cited), "answered": _mean(answered), "correct": _mean(correct),
            "support_check": {"settled_supported": _mean(sure), "correct_when_supported": _mean(correct[sure]),
                              "settled_unsupported": _mean(refuted), "correct_when_unsupported":
                                  _mean(correct[refuted]),
                              "auroc": round(cal.auroc(p_support, correct), 3)}}, out


def agent_qa(conn: psycopg.Connection, brain: Any, llm: Ollama, model: str, grader: Judge, qas: Sequence[QA], n: int,
             rng: random.Random) -> tuple[dict, list[dict]]:
    """The tool-using test agent against the one-call `ask` pipeline, on the same held-out questions as `qa`: graded
    by the same large-model grader; plus tool calls, tokens the agent read, time, and whether the gold email is
    among the cited ids (citations as ids, not parsed text)."""
    from . import research

    pool, ids = answerable(conn, qas)
    group = groups(conn, [ids[q.ref] for q in pool])
    pool = [q for q in pool if split_of(group[ids[q.ref]]) == "test"]
    rows = []
    for q in rng.sample(pool, min(n, len(pool))):
        row: dict = {"qid": q.qid, "question": q.question, "reference": q.gold, "gold_item": ids[q.ref]}
        for mode in ("ask", "agent"):
            t0 = time.perf_counter()
            if mode == "ask":
                a = brain.ask(q.question)
                answer, cited, calls, tokens = a["answer"], a["cited_ids"], 1, None
            else:
                r = research.run(llm, model, brain, q.question)
                answer, cited, calls, tokens = r.answer, list(r.cited_ids), len(r.calls), r.tool_tokens
            grade = grader.ask(noul("matches", MATCHES), f"Question: {q.question}\nReference answer: {q.gold}\n"
                                                         f"Response: {answer}", f"qa:{q.qid}")
            row[mode] = {"answer": answer, "cited": cited, "correct": grade.value == "yes", "calls": calls,
                         "tool_tokens": tokens, "seconds": round(time.perf_counter() - t0, 2),
                         "gold_cited": ids[q.ref] in cited}
        rows.append(row)

    def summary(mode: str) -> dict:
        rs = [r[mode] for r in rows]
        secs = sorted(r["seconds"] for r in rs)
        toks = sorted(r["tool_tokens"] for r in rs if r["tool_tokens"] is not None)
        return {"correct": _mean(np.array([r["correct"] for r in rs], float)),
                "gold_cited": _mean(np.array([r["gold_cited"] for r in rs], float)),
                "calls_mean": round(float(np.mean([r["calls"] for r in rs])), 2) if rs else None,
                "tool_tokens_p50": toks[len(toks) // 2] if toks else None,
                "seconds_p50": secs[len(secs) // 2] if secs else None}
    return {"questions": len(rows), "ask": summary("ask"), "agent": summary("agent")}, rows


def _mean(x: np.ndarray) -> float | None:
    return round(float(x.mean()), 3) if len(x) else None


def agent_benchmark(llm: Ollama, model: str, judge: Judge, tasks: Sequence[wb.Task], think: bool = False,
                    on_task: Callable[[dict], None] | None = None) -> tuple[dict, list[dict]]:
    """WorkBench tasks (call inside `wb.sandbox`). The agent runs each task once with no gate; then each policy's
    gate replays the recorded calls in order — a check depends only on the request, the call and the state so far —
    and WorkBench grades what that policy lets run. The owner is an oracle approving exactly the calls the task
    needs. Not captured: an agent told 'no' might recover, or try something else (LR §11)."""
    rows, failed = [], []
    for task in tasks:
        try:
            tools = {t.name: t for t in wb.tools(task.domains)}
            wb.reset()
            r = ag.run(llm, model, wb.SYSTEM, task.request, list(tools.values()), None, f"wb:{task.id}", think)
            want = wb.wanted(task)
            row = {"task": task.id, "request": task.request, "outcome": list(task.outcome), "turns": r.turns,
                   "answer": r.answer, "calls": [{"tool": s.tool, "args": s.args, "ran": s.ran,
                                                  "observation": s.observation[:300]} for s in r.steps],
                   "policies": {name: _replay(task, r, tools, want, judge, p) for name, p in POLICIES.items()}}
        except Exception as e:          # e.g. the model server dropped: report it, and grade the other tasks
            failed.append({"task": task.id, "error": f"{type(e).__name__}: {e}"})
            continue
        rows.append(row)
        if on_task:
            on_task(row)
    n = max(len(rows), 1)
    summary = {name: {"correct": round(sum(r["policies"][name]["correct"] for r in rows) / n, 3),
                      "harmful": round(sum(r["policies"][name]["harmful"] for r in rows) / n, 3),
                      "owner_prompts_per_task": round(sum(r["policies"][name]["prompts"] for r in rows) / n, 2),
                      "stopped_calls": sum(r["policies"][name]["stopped"] for r in rows)} for name in POLICIES}
    confusion: dict[str, int] = {}                  # the intent judge on every state-changing call it saw
    for r in rows:
        for c in r["policies"]["judge + owner (default autonomy)"]["checks"]:
            key = f"{'wanted' if c['wanted'] else 'unwanted'} -> {c['verdict']}"
            confusion[key] = confusion.get(key, 0) + 1
    return {"tasks": len(rows), "failed": failed, "policies": summary,
            "intent_judge": dict(sorted(confusion.items()))}, rows


def _replay(task: wb.Task, r: ag.Run, tools: dict[str, Tool], want: set[tuple], judge: Judge,
            policy: tuple[bool, int] | None) -> dict:
    prompts = 0

    def owner(request: str, tool: Tool, args: dict, verdict: object) -> bool:
        nonlocal prompts
        prompts += 1
        return wb.canonical(tool.name, args) in want

    gate = None if policy is None else Gate(judge if policy[0] else None, owner, policy[1])
    kept, checks = [], []
    wb.reset()
    for i, s in enumerate(s for s in r.steps if s.ran):
        tool = tools[s.tool]
        check = gate.check(task.request, tool, s.args, f"wb:{task.id}:{i}") if gate else None
        if check is None or check.allowed:
            kept.append((s.tool, s.args))
            if tool.effect != "read":
                with contextlib.suppress(Exception):    # the state later previews see; grading re-runs the calls
                    tool.run(**s.args)
        if check is not None and check.tier > 0:
            v = check.verdict
            checks.append({"tool": s.tool, "wanted": wb.canonical(s.tool, s.args) in want, "reason": check.reason,
                           "verdict": "no judge" if v is None else (v.value or "invalid") + ("" if v.settled
                                                                                           else " (unsure)"),
                           "p_yes": None if v is None else round(v.probs.get("yes", 0.0), 3)})
    correct, harmful = wb.grade(task, kept, r.answer is not None)
    return {"correct": correct, "harmful": harmful, "prompts": prompts, "checks": checks,
            "stopped": sum(1 for c in checks if c["reason"] not in ("auto", "approved"))}


def _band(kind: str, probs: np.ndarray, y: np.ndarray, target: float) -> tuple[float, float]:
    if kind == "noul":
        return cal.noul_band(probs[:, 0], y == 0, target)
    return 0.0, cal.top_band(probs.max(axis=1), probs.argmax(axis=1) == y, target)


def _settled(kind: str, probs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    if kind == "noul":
        return (probs[:, 0] >= hi) | (probs[:, 0] <= lo)
    return probs.max(axis=1) >= hi


def _acc(probs: np.ndarray, y: np.ndarray, mask: np.ndarray) -> float | None:
    return round(float((probs.argmax(1) == y)[mask].mean()), 3) if mask.any() else None
