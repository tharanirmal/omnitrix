"""The agent board: messages between agents, shown live as the agent chat room."""
from __future__ import annotations

from psycopg.types.json import Jsonb

from .clock import Clock
from .db import Database
from .ids import new_id
from .schemas import BoardMessage

CHANNEL = "omnitrix_board"


class Board:
    def __init__(self, db: Database, clock: Clock):
        self.db = db
        self.clock = clock

    async def post(self, from_agent: str, text: str, *, to_agent: str | None = None,
                   correlation_id: str | None = None, refs: dict[str, str] | None = None) -> BoardMessage:
        msg = BoardMessage(message_id=new_id("message"), from_agent=from_agent, to_agent=to_agent,
                           correlation_id=correlation_id, text=text, refs=refs or {}, at=self.clock.now())
        async with self.db.connection() as conn:
            await conn.execute(
                "INSERT INTO board_messages (id, from_agent, to_agent, correlation_id, text, refs, at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (msg.message_id, msg.from_agent, msg.to_agent, msg.correlation_id, msg.text, Jsonb(msg.refs),
                 msg.at))
            await conn.execute("SELECT pg_notify(%s, %s)", (CHANNEL, msg.message_id))
        return msg

    async def thread(self, correlation_id: str) -> list[BoardMessage]:
        rows = await self.db.fetch("SELECT * FROM board_messages WHERE correlation_id = %s ORDER BY recorded_at",
                                   (correlation_id,))
        return [_row_to_message(r) for r in rows]

    async def recent(self, limit: int = 50) -> list[BoardMessage]:
        rows = await self.db.fetch("SELECT * FROM board_messages ORDER BY recorded_at DESC LIMIT %s", (limit,))
        return [_row_to_message(r) for r in reversed(rows)]


def _row_to_message(row: dict) -> BoardMessage:
    return BoardMessage(message_id=row["id"], from_agent=row["from_agent"], to_agent=row["to_agent"],
                        correlation_id=row["correlation_id"], text=row["text"], refs=row["refs"], at=row["at"])
