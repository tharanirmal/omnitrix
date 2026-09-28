"""Action: tools run only through a gate (LR §11).

Code sets the risk tier from what a tool does (read < internal change < external communication < destructive).
The large model checks each state-changing action against what the owner asked — seeing only the request and a
preview of the action (the call with its own arguments, since judging an email means reading what it says, and the
record it touches without that record's free text), never retrieved text at large (LR §11.1, context
minimization) — and can only add friction, never remove it: an action it confidently judges
inconsistent is blocked, and one it is unsure about goes to the owner whatever the autonomy setting. Actions above
the auto tier (the owner's autonomy setting) wait for the owner's approval.
Every check is a judge question, so it lands in the hash-chained ledger with the rest of the brain's decisions."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from .judge import Judge, Verdict, noul

Effect = Literal["read", "internal", "external", "destructive"]
TIER: dict[Effect, int] = {"read": 0, "internal": 1, "external": 2, "destructive": 3}
INTENT = ("Is the proposed action one of the steps the owner's request asks for, applied to the right people and "
          "records? A request may need several actions; judge only this one. Answer no if it targets someone or "
          "something the request does not mean, or does something the request does not ask for.")


@dataclass(frozen=True)
class Tool:
    name: str
    effect: Effect
    run: Callable[..., Any]
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    preview: Callable[[dict[str, Any]], str] | None = None     # plain description of what a call would touch

    @property
    def schema(self) -> dict[str, Any]:
        """The function-calling schema the agent's model sees."""
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


def describe(tool: Tool, args: dict[str, Any]) -> str:
    call = f"{tool.name}({json.dumps(args, sort_keys=True, default=str)})"
    return tool.preview(args) if tool.preview else call


@dataclass(frozen=True)
class Check:
    allowed: bool
    tier: int
    reason: str                 # 'read-only', 'auto', 'approved', 'awaiting approval', 'blocked: ...'
    verdict: Verdict | None = None


class Gate:
    """`judge` asks the intent question (give it the large model); `approve(request, tool, args, verdict)` is the
    owner — an interactive prompt, or a fixed policy in a benchmark — shown the judge's verdict if there is one;
    tiers up to `auto_tier` run without asking."""

    def __init__(self, judge: Judge | None,
                 approve: Callable[[str, Tool, dict, Verdict | None], bool] | None = None,
                 auto_tier: int = TIER["internal"]):
        self.judge, self.approve, self.auto_tier = judge, approve, auto_tier

    def check(self, request: str, tool: Tool, args: dict[str, Any], subject: str) -> Check:
        tier, v = TIER[tool.effect], None
        if tier == 0:
            return Check(True, 0, "read-only")
        if self.judge is not None:
            v = self.judge.ask(noul("intent", INTENT),
                               f"Owner's request: {request}\nProposed action: {describe(tool, args)}", subject)
            if v.settled and v.value == "no":
                return Check(False, 4, f"blocked: judged inconsistent with the request (p={v.p:.2f})", v)
        if tier <= self.auto_tier and (v is None or v.settled):   # unsure about intent: the owner decides,
            return Check(True, tier, "auto", v)                     # whatever the autonomy setting
        if self.approve is not None and self.approve(request, tool, args, v):
            return Check(True, tier, "approved", v)
        return Check(False, tier, "awaiting approval", v)
