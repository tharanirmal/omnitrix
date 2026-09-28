"""The brain's tools over MCP (Model Context Protocol), stdio transport: one JSON-RPC message per line on stdin and
stdout, logs on stderr. Enough of the protocol for any MCP client (Claude Code, Claude Desktop, …) to list and call
the tools: initialize, ping, tools/list, tools/call. No third-party SDK: the protocol is small."""
from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from typing import Any, TextIO

from .act import Tool

PROTOCOL = "2025-06-18"


def handle(message: dict[str, Any], tools: dict[str, Tool]) -> dict[str, Any] | None:
    """One request in, one response out (None for notifications)."""
    method, rid = message.get("method", ""), message.get("id")
    if rid is None:                                     # a notification (e.g. notifications/initialized)
        return None
    if method == "initialize":
        version = message.get("params", {}).get("protocolVersion", PROTOCOL)
        return _ok(rid, {"protocolVersion": version, "capabilities": {"tools": {}},
                         "serverInfo": {"name": "engram", "version": "0.3"},
                         "instructions": "Tools over the owner's second brain. Cite the ids results carry."})
    if method == "ping":
        return _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, {"tools": [{"name": t.name, "description": t.description, "inputSchema": t.parameters}
                                   for t in tools.values()]})
    if method == "tools/call":
        params = message.get("params", {})
        tool = tools.get(params.get("name", ""))
        if tool is None:
            return _error(rid, -32602, f"unknown tool {params.get('name')!r}")
        try:
            text, failed = tool.run(**(params.get("arguments") or {})), False
        except Exception as e:                          # a tool's failure is the agent's to see, not a crash
            text, failed = f"{type(e).__name__}: {e}", True
        return _ok(rid, {"content": [{"type": "text", "text": text}], "isError": failed})
    return _error(rid, -32601, f"method not found: {method}")


def serve(tools: Iterable[Tool], stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    by_name = {t.name: t for t in tools}
    for line in stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line), by_name)
        except json.JSONDecodeError:
            reply = _error(None, -32700, "parse error")
        if reply is not None:
            stdout.write(json.dumps(reply, default=str) + "\n")
            stdout.flush()


def _ok(rid: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}
