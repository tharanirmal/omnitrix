import asyncio
import json

import pytest

from omnitrix.config import Settings
from omnitrix.core.schemas import TaskCandidateList
from omnitrix.llm import LLM, StructuredOutputError
from omnitrix.llm.ollama import ChatResult
from omnitrix.llm.queue import ModelQueue

GOOD = json.dumps({"tasks": [{"title": "Send quote to Mehta", "action_type": "send", "due_text": "by Thursday",
                              "due_at": None, "people": ["Mehta"], "waiting_on_text": None,
                              "evidence_quote": "send me the quote by Thursday", "confidence": 0.9}]})
BAD = json.dumps({"tasks": [{"title": "Send quote", "action_type": "email", "evidence_quote": "x",
                             "confidence": 0.9}]})


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def chat(self, model, messages, *, format=None, think=None, options=None):
        self.calls.append({"model": model, "messages": list(messages), "format": format})
        return ChatResult(self.replies.pop(0), model, 10, 5, 1)

    async def close(self):
        pass


async def test_urgent_jobs_overtake_waiting_ones():
    queue = ModelQueue(concurrency=1)
    order = []
    gate = asyncio.Event()

    async def blocker():
        await gate.wait()
        order.append("first")

    def job(name):
        async def run():
            order.append(name)
        return run

    running = asyncio.create_task(queue.submit("normal", blocker))
    await asyncio.sleep(0)  # the worker picks up the blocker
    waiting = [asyncio.create_task(queue.submit(p, job(n)))
               for p, n in [("low", "low"), ("normal", "normal"), ("urgent", "urgent"), ("high", "high")]]
    await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(running, *waiting)
    await queue.stop()
    assert order == ["first", "urgent", "high", "normal", "low"]


async def test_structured_sends_an_inline_schema_and_uses_the_right_model():
    client = FakeClient([GOOD])
    llm = LLM(Settings(), client=client)
    result = await llm.structured("fast", "extract", "text", TaskCandidateList)
    await llm.close()
    assert result.tasks[0].title == "Send quote to Mehta"
    assert client.calls[0]["model"] == Settings().model_fast
    assert "$ref" not in json.dumps(client.calls[0]["format"])


async def test_structured_retries_once_with_the_validation_error():
    client = FakeClient([BAD, GOOD])
    llm = LLM(Settings(), client=client)
    result = await llm.structured("fast", "extract", "text", TaskCandidateList)
    await llm.close()
    assert len(result.tasks) == 1 and llm.usage.retries == 1
    feedback = client.calls[1]["messages"][-1]["content"]
    assert "did not match" in feedback and "action_type" in feedback


async def test_structured_gives_up_after_the_retry():
    llm = LLM(Settings(), client=FakeClient([BAD, BAD]))
    with pytest.raises(StructuredOutputError):
        await llm.structured("fast", "extract", "text", TaskCandidateList)
    await llm.close()
