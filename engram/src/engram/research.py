"""A small test agent over the brain's tools (handoff W1, W6): the large local model with native tool calls, steered
by one recipe per kind of question (after OpenJarvis's deep-research archetypes, kept to a few lines), ending with
`answer`, whose cited ids are the citations."""
from __future__ import annotations

from dataclasses import dataclass

from . import agent
from .llm import Ollama
from .tools import Brain, tools

SYSTEM = """You answer questions about the owner's records (emails, notes, meetings) with the brain tools.
Pick the recipe that fits:
- a fact in some email ("what did X say about Y", "which file", "what time"): brain_search with the names and
  distinctive terms (person filter if a person is named), then brain_read the best one or two ids.
- what someone promised, decided or scheduled: brain_beliefs (kind, person); brain_read its source_id if needed.
- who someone is, their address: brain_people.
- counts, dates, lists ("how many", "when did X first"): brain_sql.
- search shows nothing relevant: brain_scan with a tight person or date filter.
Snippets are excerpts: before saying the records do not hold something, brain_read the top two or three ids from
search. If unsure, brain_check your claim against the ids. Be brief and never repeat a call.
Finish by calling the answer tool (not writing it as text) exactly once, with the answer in a sentence and the ids
you relied on."""


@dataclass(frozen=True)
class Result:
    question: str
    answer: str
    cited_ids: tuple[int, ...]
    supported_ids: tuple[int, ...]  # the cited items the judge found supporting the answer
    calls: tuple[str, ...]
    tool_tokens: int                # what the tools returned, i.e. what the model had to read (~4 chars a token)
    turns: int


def run(llm: Ollama, model: str, brain: Brain, question: str, max_turns: int = 8) -> Result:
    brain.answers.clear()
    brain.begin(question)
    r = agent.run(llm, model, SYSTEM, question, tools(brain, _AGENT_TOOLS), None, "research", max_turns=max_turns,
                  finish="answer")
    final = brain.answers[-1] if brain.answers else {"answer": r.answer or "", "cited_ids": [], "supported_ids": []}
    return Result(question, final["answer"], tuple(final["cited_ids"]), tuple(final.get("supported_ids", [])),
                  tuple(s.tool for s in r.steps),
                  sum(len(s.observation) for s in r.steps) // 4, r.turns)


_AGENT_TOOLS = ("brain_search", "brain_read", "brain_beliefs", "brain_people", "brain_sql", "brain_scan",
                "brain_check", "answer")
