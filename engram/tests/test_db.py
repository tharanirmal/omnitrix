"""Migrations: a new brain's database is created on first use."""
import uuid

import psycopg
import pytest

from engram.config import settings
from engram.db import migrate


def test_migrate_creates_a_missing_brain():
    url = f"{settings.database_url.rsplit('/', 1)[0]}/engram_test_{uuid.uuid4().hex[:8]}"
    try:
        applied = migrate(url)
    except psycopg.OperationalError as e:
        pytest.skip(f"engram Postgres not reachable: {e}")
    try:
        assert applied[0] == "001_core.sql" and migrate(url) == []          # created, then already up to date
    finally:
        with psycopg.connect(url.rsplit("/", 1)[0] + "/postgres", autocommit=True) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {url.rsplit('/', 1)[1]} WITH (FORCE)")
