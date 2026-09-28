"""Prefixed, roughly time-ordered IDs: task_0193f2a1c4e8b27d9a1c."""
import secrets
import time

PREFIXES = {
    "source": "src", "email": "em", "document": "doc", "chunk": "chk", "entity": "ent", "relation": "rel",
    "task": "task", "meeting_request": "mr", "calendar_event": "cal", "plan": "plan", "plan_item": "pi",
    "promise": "p", "decision": "dec", "lesson": "les", "event": "evt", "message": "msg", "run": "run",
    "tool_call": "tc", "approval": "appr", "policy": "pol", "story": "story",
}


def new_id(kind: str) -> str:
    prefix = PREFIXES.get(kind, kind)
    return f"{prefix}_{int(time.time() * 1000):011x}{secrets.token_hex(4)}"
