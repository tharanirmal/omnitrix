"""The local model server (Ollama). Nothing here calls a cloud service."""
from __future__ import annotations

import json

import httpx


class Ollama:
    def __init__(self, url: str, timeout: float = 300.0, keep_alive: str = "30m"):
        self._http = httpx.Client(base_url=url.rstrip("/"), timeout=timeout)
        self.keep_alive = keep_alive

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Ollama:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        r = self._http.post("/api/embed", json={"model": model, "input": texts, "keep_alive": self.keep_alive})
        r.raise_for_status()
        return r.json()["embeddings"]

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None, fmt: dict | None = None,
             think: bool = False, max_tokens: int = 1024) -> dict:
        """One assistant message; with `tools` it may carry `tool_calls` (native tool calling), with `fmt` its
        content is constrained to that JSON schema (structured outputs)."""
        body = {"model": model, "stream": False, "think": think, "keep_alive": self.keep_alive, "messages": messages,
                "options": {"temperature": 0, "num_predict": max_tokens}}
        if tools:
            body["tools"] = tools
        if fmt:
            body["format"] = fmt
        r = self._http.post("/api/chat", json=body)
        r.raise_for_status()
        return r.json()["message"]

    def generate_json(self, model: str, system: str, user: str, schema: dict, max_tokens: int = 600) -> dict:
        """One structured answer, constrained to `schema`; thinking off."""
        msg = self.chat(model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                        fmt=schema, max_tokens=max_tokens)
        return json.loads(msg["content"])
