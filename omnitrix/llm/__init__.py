"""The one way agents talk to a model: `LLM.structured()` for fixed-format answers, `LLM.text()` for
prose, `LLM.embed()` for search vectors. Every call goes through the priority queue."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from omnitrix.config import Settings
from omnitrix.core.schemas import Priority, inline_schema

from .ollama import ChatResult, OllamaClient, OllamaError
from .queue import ModelQueue

Role = Literal["main", "fast"]
M = TypeVar("M", bound=BaseModel)

__all__ = ["LLM", "LLMUsage", "OllamaClient", "OllamaError", "ModelQueue", "StructuredOutputError"]


class StructuredOutputError(RuntimeError):
    def __init__(self, message: str, last_content: str):
        super().__init__(message)
        self.last_content = last_content


@dataclass
class LLMUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    retries: int = 0
    by_model: dict[str, int] = field(default_factory=dict)

    def add(self, r: ChatResult) -> None:
        self.calls += 1
        self.input_tokens += r.input_tokens
        self.output_tokens += r.output_tokens
        self.duration_ms += r.duration_ms
        self.by_model[r.model] = self.by_model.get(r.model, 0) + 1


class LLM:
    def __init__(self, settings: Settings, client: OllamaClient | None = None, queue: ModelQueue | None = None):
        self.settings = settings
        self.client = client or OllamaClient(settings.ollama_url, settings.llm_timeout_s, settings.llm_keep_alive)
        self.queue = queue or ModelQueue(settings.llm_concurrency)
        self.usage = LLMUsage()

    async def close(self) -> None:
        await self.queue.stop()
        await self.client.close()

    def _options(self, temperature: float) -> dict:
        return {"temperature": temperature, "num_ctx": self.settings.llm_num_ctx}

    async def _chat(self, role: Role, messages: list[dict], priority: Priority, *, format=None,
                    temperature: float = 0.1) -> ChatResult:
        model = self.settings.model_for(role)
        result = await self.queue.submit(priority, lambda: self.client.chat(
            model, messages, format=format, think=self.settings.llm_think, options=self._options(temperature)))
        self.usage.add(result)
        return result

    async def structured(self, role: Role, system: str, user: str, schema: type[M], *,
                         priority: Priority = "normal", retries: int = 1) -> M:
        """Ask for an answer that must match `schema`. Ollama constrains the output to the JSON schema;
        pydantic then validates it, and on failure the model is shown the error and asked again."""
        fmt = inline_schema(schema)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        content = ""
        for attempt in range(retries + 1):
            result = await self._chat(role, messages, priority, format=fmt, temperature=0.0)
            content = result.content
            try:
                return schema.model_validate_json(content)
            except ValidationError as e:
                if attempt == retries:
                    raise StructuredOutputError(f"{schema.__name__} invalid after {retries + 1} tries: {e}",
                                                content) from e
                self.usage.retries += 1
                messages += [{"role": "assistant", "content": content},
                             {"role": "user", "content": "That JSON did not match the required format:\n"
                              f"{_short_errors(e)}\nReply again with corrected JSON only."}]
        raise AssertionError("unreachable")

    async def text(self, role: Role, system: str, user: str, *, priority: Priority = "normal",
                   temperature: float = 0.4) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return (await self._chat(role, messages, priority, temperature=temperature)).content.strip()

    async def embed(self, texts: list[str], *, priority: Priority = "normal") -> list[list[float]]:
        vectors = await self.queue.submit(priority, lambda: self.client.embed(self.settings.model_embed, texts))
        if vectors and len(vectors[0]) != self.settings.embed_dim:
            raise OllamaError(f"{self.settings.model_embed} returns {len(vectors[0])}-dim vectors but "
                              f"OMNITRIX_EMBED_DIM is {self.settings.embed_dim}; the database expects the latter")
        return vectors


def _short_errors(e: ValidationError) -> str:
    return json.dumps([{"at": ".".join(map(str, err["loc"])), "problem": err["msg"]} for err in e.errors()[:8]])
