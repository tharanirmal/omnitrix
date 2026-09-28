"""One priority queue in front of the model: the laptop has one GPU, so requests run one (or a few) at a
time and an urgent meeting reply overtakes a background document scan."""
from __future__ import annotations

import asyncio
import itertools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from omnitrix.core.schemas import PRIORITY_RANK, Priority

T = TypeVar("T")


class ModelQueue:
    def __init__(self, concurrency: int = 1):
        self.concurrency = concurrency
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._seq = itertools.count()
        self._workers: list[asyncio.Task] = []

    def start(self) -> None:
        if not self._workers:
            self._workers = [asyncio.create_task(self._worker()) for _ in range(self.concurrency)]

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []

    @property
    def waiting(self) -> int:
        return self._queue.qsize()

    async def submit(self, priority: Priority, job: Callable[[], Awaitable[T]]) -> T:
        self.start()
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        # lower tuple sorts first: urgent (rank 3) -> -3, then first come first served
        await self._queue.put((-PRIORITY_RANK[priority], next(self._seq), job, future))
        return await future

    async def _worker(self) -> None:
        while True:
            _, _, job, future = await self._queue.get()
            try:
                if not future.cancelled():
                    future.set_result(await job())
            except Exception as e:  # noqa: BLE001 - handed to the caller
                if not future.cancelled():
                    future.set_exception(e)
            finally:
                self._queue.task_done()


async def run_all(queue: ModelQueue, jobs: list[tuple[Priority, Callable[[], Awaitable[Any]]]]) -> list[Any]:
    return await asyncio.gather(*(queue.submit(p, j) for p, j in jobs))
