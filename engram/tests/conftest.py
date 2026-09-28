"""Shared fixtures. Database tests run against a throwaway database per test module on the engram Postgres
(docker compose up -d) and are skipped when it is not reachable."""
from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections.abc import Iterator

import psycopg
import pytest

from engram.config import settings
from engram.db import migrate


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    server = settings.database_url.rsplit("/", 1)[0]
    name = f"engram_test_{uuid.uuid4().hex[:8]}"
    try:
        with psycopg.connect(f"{server}/postgres", autocommit=True, connect_timeout=3) as conn:
            conn.execute(f"CREATE DATABASE {name}")
    except psycopg.OperationalError as e:
        pytest.skip(f"engram Postgres not reachable: {e}")
    url = f"{server}/{name}"
    migrate(url)
    yield url
    with psycopg.connect(f"{server}/postgres", autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words vectors: texts sharing words are close. Keeps tests free of model servers."""
    out = []
    for t in texts:
        v = [0.0] * 1024
        for w in re.findall(r"[a-z0-9]+", t.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 1024] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out
