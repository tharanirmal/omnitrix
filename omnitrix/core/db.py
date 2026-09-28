"""Postgres access: a small async pool, migrations, and the settings table."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


class Database:
    def __init__(self, url: str, min_size: int = 1, max_size: int = 10):
        self.url = url
        self.pool = AsyncConnectionPool(url, min_size=min_size, max_size=max_size, open=False,
                                        kwargs={"row_factory": dict_row})

    async def open(self) -> Database:
        await self.pool.open(wait=True, timeout=10)
        return self

    async def close(self) -> None:
        await self.pool.close()

    async def __aenter__(self) -> Database:
        return await self.open()

    async def __aexit__(self, *exc) -> None:
        await self.close()

    def connection(self):
        return self.pool.connection()

    async def fetch(self, sql: str, params: Any = None) -> list[dict]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchall()

    async def fetchrow(self, sql: str, params: Any = None) -> dict | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchone()

    async def execute(self, sql: str, params: Any = None) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(sql, params)

    # ------------------------------------------------------------------------------------ migrations

    async def migrate(self) -> list[str]:
        """Apply migrations/*.sql that have not run yet, each in its own transaction."""
        applied: list[str] = []
        async with self.pool.connection() as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                               "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
            done = {r["name"] for r in await (await conn.execute("SELECT name FROM schema_migrations")).fetchall()}
            for path in sorted(MIGRATIONS.glob("*.sql")):
                if path.name in done:
                    continue
                async with conn.transaction():
                    await conn.execute(path.read_text())
                    await conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                applied.append(path.name)
        return applied

    async def reset(self) -> None:
        """Drop everything in the public schema. Local development only."""
        async with self.pool.connection() as conn:
            await conn.execute("DROP SCHEMA public CASCADE")
            await conn.execute("CREATE SCHEMA public")

    async def applied_migrations(self) -> list[str]:
        rows = await self.fetch("SELECT name FROM schema_migrations ORDER BY name")
        return [r["name"] for r in rows]

    # -------------------------------------------------------------------------------------- settings

    async def get_setting(self, key: str) -> Any:
        row = await self.fetchrow("SELECT value FROM settings WHERE key = %s", (key,))
        return row["value"] if row else None

    async def set_setting(self, key: str, value: Any) -> None:
        await self.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (%s, %s, now()) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
            (key, Jsonb(value)))
