import os
from zoneinfo import ZoneInfo

import psycopg
import pytest

from omnitrix.config import get_settings
from omnitrix.core.clock import Clock
from omnitrix.core.db import Database

TZ = ZoneInfo("Asia/Kolkata")
TEST_DB = "omnitrix_test"


@pytest.fixture
def clock() -> Clock:
    from datetime import datetime
    c = Clock(TZ)
    c.freeze(datetime(2026, 10, 8, 8, 55, tzinfo=TZ))   # demo "today": Thu 8 Oct, 8:55 AM
    return c


def _test_url() -> str | None:
    """Create (once) and return a separate test database next to the dev one, or None if Postgres is down."""
    url = os.environ.get("OMNITRIX_TEST_DATABASE_URL")
    if url:
        return url
    base = get_settings().database_url
    try:
        with psycopg.connect(base, autocommit=True, connect_timeout=2) as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)).fetchone()
            if not exists:
                conn.execute(f"CREATE DATABASE {TEST_DB}")
    except psycopg.OperationalError:
        return None
    return base.rsplit("/", 1)[0] + "/" + TEST_DB


@pytest.fixture
async def db():
    url = _test_url()
    if url is None:
        pytest.skip("Postgres is not running (docker compose up -d)")
    database = Database(url, max_size=4)
    await database.open()
    await database.reset()
    await database.migrate()
    yield database
    await database.close()
