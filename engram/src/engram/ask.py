"""Reasoning: answer the owner's question from the brain (LR §6, §7).

Code retrieves (hybrid search). The small judge drops the items it is sure do not hold the answer and puts the
rest in order of how likely they are to hold it. The large model answers from them, citing them. The small judge
then checks the answer against each cited item. `relevant` and `supported` are the decisions it was fine-tuned on,
asked in the same words, so its calibration carries over. The owner sees how sure the brain is, and an answer no
cited item supports is marked as such."""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import psycopg

from . import index
from .index import Embed
from .judge import Judge, Verdict
from .labels import item_texts, relevant_question, supported_question
from .llm import Ollama

SYSTEM = ("You answer the owner's questions from their own records. Use only the numbered items. Answer in one or "
          "two sentences and list the numbers of the items the answer comes from. If the items do not contain the "
          "answer, say so and cite nothing.")
SCHEMA = {"type": "object", "required": ["answer", "cites"],
          "properties": {"answer": {"type": "string"}, "cites": {"type": "array", "items": {"type": "integer"}}}}
ITEM_CHARS = 2500                   # of each item shown to the answering model
SURE = 0.9                          # the judge is this sure an item holds the answer...
ENOUGH = 2                          # ...and has found this many: the rest of the results go unjudged
READ = 4                            # at most this many items go to the answering model


@dataclass(frozen=True)
class Reply:
    question: str
    answer: str
    cites: tuple[int, ...]          # items the answer comes from
    support: Verdict | None         # the judge's check against the cited item that best supports it
    considered: tuple[int, ...]     # retrieved
    kept: tuple[int, ...]           # after the relevance check
    answered_by: str = ""           # the model whose answer stands (a small model's draft, if the judge upheld it)


def ask(conn: psycopg.Connection, judge: Judge, llm: Ollama, model: str, embed: Embed | None, question: str,
        k: int = 10, *, since: datetime | None = None, until: datetime | None = None, people: Sequence[str] = (),
        direction: str | None = None, draft: str | None = None) -> Reply:
    """`draft`: a small model that answers first; its answer stands if the judge settles that the cited items
    support it, and only otherwise does `model` answer (System 1 first, applied to writing: LR §6)."""
    tag = f"ask:{hashlib.sha256(question.encode()).hexdigest()[:12]}"
    hits = index.search(conn, embed, question, k, since=since, until=until, people=people, direction=direction)
    texts = item_texts(conn, [h.item_id for h in hits])
    judged: list[tuple[index.Hit, bool, float]] = []
    for h in hits:                                  # in rank order, stopping once enough sure answers are in hand
        judged.append((h, *_relevance(judge, question, texts[h.item_id], f"item:{h.item_id}|{tag}")))
        if sum(p >= SURE for *_, p in judged) >= ENOUGH:
            break
    # the judge's relevance orders what the answering model reads (stable: ties keep the search order)
    kept = [h for h, drop, _ in sorted(judged, key=lambda j: -j[2]) if not drop][:READ]
    considered = tuple(h.item_id for h in hits)
    if not kept:
        return Reply(question, "Nothing in the brain answers this.", (), None, considered, ())
    material = "\n\n".join(f"[{i}] {h.sent_at:%Y-%m-%d}\n{texts[h.item_id][:ITEM_CHARS]}" if h.sent_at else
                           f"[{i}]\n{texts[h.item_id][:ITEM_CHARS]}" for i, h in enumerate(kept, 1))
    for m in ([draft] if draft else []) + [model]:
        try:
            out = llm.generate_json(m, SYSTEM, f"{material}\n\nQuestion: {question}", SCHEMA, max_tokens=300)
        except ValueError:                          # a draft cut off mid-JSON: the next model answers
            if m != model:
                continue
            raise
        cites = tuple(dict.fromkeys(kept[i - 1].item_id for i in out.get("cites", []) if 1 <= i <= len(kept)))
        checks = [judge.ask(supported_question(question, out["answer"]), texts[c], f"item:{c}|{tag}") for c in cites]
        support = max(checks, key=lambda v: v.probs["yes"], default=None)
        if support is not None and support.settled and support.value == "yes":
            break                                   # upheld: the larger model is not needed
    return Reply(question, out["answer"], cites, support, considered, tuple(h.item_id for h in kept), m)


def _relevance(judge: Judge, question: str, text: str, subject: str) -> tuple[bool, float]:
    """(surely irrelevant, P(relevant)), from S1 alone: the large model reads whatever is kept anyway, so an unsure
    item simply stays."""
    if judge.s1 is None:
        return False, 0.5
    a = judge.answer("S1", judge.s1, relevant_question(question), text, subject)
    return a.settled and a.value == "no", a.probs.get("yes", 0.5)
