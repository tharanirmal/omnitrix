"""Postgres access: a connection helper and a forward-only migration runner (sql/NNN_*.sql, applied in order)."""
from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

SQL_DIR = Path(__file__).parent / "sql"


@contextmanager
def connect(url: str) -> Iterator[psycopg.Connection]:
    """A connection returning rows as dicts. Commits on success, rolls back on error."""
    with psycopg.connect(url, row_factory=dict_row) as conn:
        yield conn


def migrate(url: str) -> list[str]:
    """Create the database if needed (one database per brain), then apply every migration not yet recorded in
    schema_migrations. Returns the names applied."""
    name = conninfo_to_dict(url)["dbname"]
    with psycopg.connect(make_conninfo(url, dbname="postgres"), autocommit=True) as server:
        if not server.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            with contextlib.suppress(psycopg.errors.DuplicateDatabase):     # another migrate got there first
                server.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    applied: list[str] = []
    with connect(url) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                     "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for path in sorted(SQL_DIR.glob("*.sql")):
            if path.name in done:
                continue
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied
