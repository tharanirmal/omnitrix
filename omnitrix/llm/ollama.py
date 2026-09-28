"""Minimal async client for Ollama's native API (/api/chat, /api/embed, /api/tags).

The native API is used instead of the OpenAI-compatible one because it takes a JSON schema in
`format` (structured output), `think`, per-request `options.num_ctx` and `keep_alive`."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class OllamaError(RuntimeError):
    pass


@dataclass
class ChatResult:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int


class OllamaClient:
    def __init__(self, base_url: str, timeout_s: float = 180.0, keep_alive: str = "30m"):
        self.base_url = base_url.rstrip("/")
        self.keep_alive = keep_alive
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout_s)

    async def close(self) -> None:
        await self._http.aclose()

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            r = await self._http.post(path, json=body)
        except httpx.HTTPError as e:
            raise OllamaError(f"cannot reach Ollama at {self.base_url}: {e}") from e
        if r.status_code != 200:
            raise OllamaError(f"{path} returned {r.status_code}: {r.text[:300]}")
        return r.json()

    async def chat(self, model: str, messages: list[dict[str, str]], *, format: dict | str | None = None,
                   think: bool | None = None, options: dict[str, Any] | None = None) -> ChatResult:
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": False,
                                "keep_alive": self.keep_alive, "options": options or {}}
        if format is not None:
            body["format"] = format
        if think is not None:
            body["think"] = think
        try:
            data = await self._post("/api/chat", body)
        except OllamaError as e:
            # models without a thinking mode reject the flag; ask again without it
            if think is not None and "think" in str(e).lower():
                body.pop("think")
                data = await self._post("/api/chat", body)
            else:
                raise
        return ChatResult(
            content=data.get("message", {}).get("content", ""),
            model=data.get("model", model),
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            duration_ms=int(data.get("total_duration", 0) / 1_000_000),
        )

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        data = await self._post("/api/embed", {"model": model, "input": texts, "keep_alive": self.keep_alive})
        return data["embeddings"]

    async def list_models(self) -> list[str]:
        try:
            r = await self._http.get("/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaError(f"cannot reach Ollama at {self.base_url}: {e}") from e
        return [m["name"] for m in r.json().get("models", [])]

    async def loaded_models(self) -> list[str]:
        r = await self._http.get("/api/ps")
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
