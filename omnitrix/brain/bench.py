"""Benchmark recall on questions with known answers (demo_data/brain_queries.yaml).

Strategies compared:
  brain        scoped hybrid search + graph facts (what agents use)
  vector_all   meaning search over every chunk (classic RAG)
  keyword_all  keyword search over every chunk
  everything   no retrieval - put the whole brain in the prompt (only its size is reported)
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .recall import Brain, ContextPack

QUERIES = Path(__file__).resolve().parents[2] / "demo_data" / "brain_queries.yaml"
STRATEGIES = ("brain", "vector_all", "keyword_all")


def load_queries() -> list[dict]:
    return yaml.safe_load(QUERIES.read_text())["queries"]


def matches(item_ref: dict, source: str) -> bool:
    return source in {item_ref.get("demo_id"), item_ref.get("path"), item_ref.get("filename")}


def score_pack(pack: ContextPack, q: dict) -> dict:
    expected = q["sources"]
    found = {s for s in expected if any(matches(i.ref, s) for i in pack.items)}
    first = next((rank for rank, i in enumerate(pack.items, 1) if any(matches(i.ref, s) for s in expected)), None)
    facts_expected = q.get("facts", [])
    facts_found = [f for f in facts_expected if any(x.ref == f for x in pack.facts)]
    answered = first is not None or bool(facts_found)
    return {"hit": first is not None, "answered": answered, "recall": len(found) / len(expected),
            "rr": 1 / first if first else 0.0,
            "facts_found": len(facts_found), "facts_expected": len(facts_expected),
            "tokens": pack.stats["returned_tokens"], "ms": pack.stats["total_ms"],
            "searched": pack.stats["share_searched"], "scoped": pack.stats.get("scoped", False)}


@dataclass
class StrategyResult:
    strategy: str
    rows: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        r = self.rows
        ms = sorted(x["ms"] for x in r)
        facts_exp = sum(x["facts_expected"] for x in r)
        return {
            "strategy": self.strategy,
            "hit_at_k": sum(x["hit"] for x in r) / len(r),
            "answered": sum(x["answered"] for x in r) / len(r),
            "recall": statistics.mean(x["recall"] for x in r),
            "mrr": statistics.mean(x["rr"] for x in r),
            "facts": f"{sum(x['facts_found'] for x in r)}/{facts_exp}" if facts_exp else "-",
            "tokens": statistics.mean(x["tokens"] for x in r),
            "ms_p50": statistics.median(ms),
            "ms_p95": ms[min(len(ms) - 1, round(0.95 * (len(ms) - 1)))],
            "searched": statistics.mean(x["searched"] for x in r),
            "under_1pct": sum(x["searched"] < 0.01 for x in r),
            "scoped": sum(x["scoped"] for x in r),
        }


async def run_bench(brain: Brain, k: int = 5, token_budget: int = 1200) -> tuple[list[StrategyResult], list[dict]]:
    queries = load_queries()
    await brain.refresh()
    await brain.recall("warm-up", log=False)          # load the embedding model before timing
    results = {s: StrategyResult(s) for s in STRATEGIES}
    per_query: list[dict] = []
    for q in queries:
        row = {"id": q["id"], "ask": q["ask"]}
        for s in STRATEGIES:
            pack = await brain.recall(q["ask"], agent=q.get("agent", "bench"), strategy=s, k=k,
                                      token_budget=token_budget, log=True)
            scored = score_pack(pack, q)
            results[s].rows.append(scored)
            row[s] = scored
        per_query.append(row)
    return list(results.values()), per_query
