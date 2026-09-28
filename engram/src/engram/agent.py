"""Agent: a local model works through a request with tools, one call at a time (native tool calling). Every call
passes the gate first (act.py); a call the gate stops is not run, and the model is told why."""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .act import Check, Gate, Tool, describe
from .llm import Ollama


@dataclass(frozen=True)
class Step:
    tool: str
    args: dict[str, Any]
    check: Check | None          # None: no gate
    ran: bool
    observation: str


@dataclass(frozen=True)
class Run:
    request: str
    steps: tuple[Step, ...]
    answer: str | None           # the final message; None if the turn limit was hit
    turns: int


def run(llm: Ollama, model: str, system: str, request: str, tools: Sequence[Tool], gate: Gate | None = None,
        subject: str = "act", think: bool = False, max_turns: int = 20,
        on_step: Callable[[Step], None] | None = None, finish: str | None = None) -> Run:
    """`finish`: a tool the run must end with; a model that stops without calling it is reminded once of the
    request (after OpenJarvis's forced final turn: long tool results can make a model lose the question)."""
    by_name = {t.name: t for t in tools}
    schemas = [t.schema for t in tools]
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": request}]
    steps: list[Step] = []
    refused: set[str] = set()
    reminded = False
    for turn in range(1, max_turns + 1):
        msg = llm.chat(model, messages, schemas, think=think, max_tokens=4096 if think else 1024)
        messages.append({k: msg[k] for k in ("role", "content", "tool_calls") if k in msg})
        calls = msg.get("tool_calls") or []
        if not calls:
            if finish and not any(s.tool == finish for s in steps) and not reminded:
                reminded = True
                messages.append({"role": "user", "content": f"Now call {finish} with your answer to the original "
                                                            f"request: {request}"})
                continue
            return Run(request, tuple(steps), msg.get("content", ""), turn)
        for call in calls:
            name, args = call["function"]["name"], call["function"].get("arguments") or {}
            if isinstance(args, str):                       # some models send the arguments JSON-encoded
                args = json.loads(args or "{}")
            steps.append(_step(by_name.get(name), name, args, request, gate, f"{subject}:{len(steps)}"))
            messages.append({"role": "tool", "tool_name": name, "content": steps[-1].observation})
            if on_step:
                on_step(steps[-1])
            if steps[-1].check is not None and not steps[-1].check.allowed:
                key = f"{name}{json.dumps(args, sort_keys=True, default=str)}"
                if key in refused:                          # it will not take no for an answer: stop here
                    return Run(request, tuple(steps), "Stopped: the agent repeated an action that was not allowed.",
                               turn)
                refused.add(key)
    return Run(request, tuple(steps), None, max_turns)


def _step(tool: Tool | None, name: str, args: dict[str, Any], request: str, gate: Gate | None,
          subject: str) -> Step:
    if tool is None:
        return Step(name, args, None, False, f"No tool named {name!r}.")
    try:
        check = gate.check(request, tool, args, subject) if gate else None
    except Exception as e:              # the gate could not decide (model server or database down): fail closed
        return Step(name, args, None, False, f"Not done: the gate failed ({type(e).__name__}: {e}).")
    if check is not None and not check.allowed:
        return Step(name, args, check, False, f"Not done ({check.reason}). What the gate saw:\n{describe(tool, args)}\n"
                                              "Fix the call if it is wrong; otherwise tell the owner what you would do "
                                              "instead.")
    try:
        return Step(name, args, check, True, str(tool.run(**args)))
    except Exception as e:              # a bad call (e.g. an unknown argument) is the model's to fix, not a crash
        return Step(name, args, check, False, f"Error: {type(e).__name__}: {e}")
