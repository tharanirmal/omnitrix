"""Profiles: each one a brain, and each brain its own Postgres database. A profile is a name, the database it opens,
an avatar colour and a passphrase hash (scrypt, a salt per profile). The registry is a small JSON file next to the
data (data/profiles.json, mode 0600). Sessions live in memory only: a random token in an HttpOnly, SameSite=Strict
cookie, forgotten after an idle timeout or on restart. Wrong passphrases lock a profile for a while, doubling."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

NAME = re.compile(r"^[a-z][a-z0-9_]{0,30}$")          # a profile name, and a database name made from it
RESERVED = {"postgres", "template0", "template1", "engram_meta", "engram_reader"}
COLORS = ("s0", "s1", "s2", "h")                      # avatar colours: the tier signal tokens
SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1}               # ~60 ms and 32 MiB per attempt
IDLE = 30 * 60.0                                      # a session ends after this long without a request
LIFETIME = 12 * 3600.0                                # and after this long in any case
FREE_TRIES, LOCK = 5, 30.0                            # after 5 wrong passphrases: 30 s, then 60 s, 120 s … (≤ 15 min)
COOKIE = "engram_session"


class Locked(Exception):
    def __init__(self, seconds: float):
        super().__init__(f"too many wrong passphrases: try again in {seconds:.0f} s")
        self.seconds = seconds


class WrongPassphrase(Exception):
    def __init__(self, remaining: int):
        super().__init__("wrong passphrase")
        self.remaining = remaining


@dataclass
class Session:
    profile: str
    created: float
    seen: float


def _hash(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(passphrase.encode(), salt=salt, n=n, r=r, p=p, maxmem=64 << 20, dklen=32)


class Profiles:
    """The registry, the sessions and the attempt counters. Thread-safe; the file is rewritten atomically."""

    def __init__(self, path: Path, clock=time.monotonic):
        self.path, self.clock = path, clock
        self.lock = threading.Lock()
        self.sessions: dict[str, Session] = {}
        self.failures: dict[str, tuple[int, float]] = {}     # profile -> (wrong tries in a row, locked until)
        self.checking: dict[str, threading.Lock] = {}          # one passphrase check at a time per profile, so
                                                               # parallel guesses cannot outrun the lock

    # ---------------------------------------------------------------------------------------------- registry

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {"profiles": []}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, self.path)

    def list(self) -> list[dict]:
        """Every profile without its secrets: name, database, colour."""
        return [{"name": p["name"], "database": p["database"], "color": p["color"]} for p in self._read()["profiles"]]

    def get(self, name: str) -> dict | None:
        return next((p for p in self._read()["profiles"] if p["name"] == name), None)

    @staticmethod
    def check(name: str, passphrase: str, color: str) -> None:
        """Raise ValueError unless these make a valid profile."""
        if not NAME.match(name) or name in RESERVED:
            raise ValueError("a name is a lower-case letter, then letters, digits or _ (at most 31)")
        if len(passphrase) < 8:
            raise ValueError("a passphrase needs at least 8 characters")
        if len(passphrase) > 1024:
            raise ValueError("a passphrase is at most 1024 characters")
        if color not in COLORS:
            raise ValueError(f"colour is one of {', '.join(COLORS)}")

    def add(self, name: str, passphrase: str, database: str | None = None, color: str = "s1") -> dict:
        """Register a profile for `database` (default: a database named like the profile). The caller creates or
        migrates the database; this only records who may open it."""
        database = database or name
        self.check(name, passphrase, color)
        if not NAME.match(database) or database in RESERVED:
            raise ValueError(f"not a database a brain can live in: {database!r}")
        salt = secrets.token_bytes(16)
        record = {"name": name, "database": database, "color": color, "salt": salt.hex(), **SCRYPT,
                  "hash": _hash(passphrase, salt, **SCRYPT).hex(),
                  "created": datetime.now().isoformat(timespec="seconds")}
        with self.lock:
            data = self._read()
            if any(p["name"] == name for p in data["profiles"]):
                raise ValueError(f"there is already a brain called {name}")
            if any(p["database"] == database for p in data["profiles"]):
                raise ValueError(f"database {database} already belongs to another profile")
            data["profiles"].append(record)
            self._write(data)
        return {"name": name, "database": database, "color": color}

    def remove(self, name: str) -> bool:
        with self.lock:
            data = self._read()
            keep = [p for p in data["profiles"] if p["name"] != name]
            if len(keep) == len(data["profiles"]):
                return False
            data["profiles"] = keep
            self._write(data)
            self.sessions = {t: s for t, s in self.sessions.items() if s.profile != name}
        return True

    # -------------------------------------------------------------------------------------- unlock, sessions

    def unlock(self, name: str, passphrase: str) -> str:
        """A new session token for the right passphrase. Raises LookupError (no such profile), Locked or
        WrongPassphrase. The hash is computed even for an unknown profile, so timing does not tell them apart."""
        with self.lock:
            gate = self.checking.setdefault(name, threading.Lock())
        with gate:
            return self._unlock(name, passphrase)

    def _unlock(self, name: str, passphrase: str) -> str:
        p = self.get(name)
        now = self.clock()
        with self.lock:
            tries, until = self.failures.get(name, (0, 0.0))
            if until > now:
                raise Locked(until - now)
        if p is None:
            _hash(passphrase, b"\0" * 16, **SCRYPT)
            raise LookupError("no such brain")
        ok = hmac.compare_digest(_hash(passphrase, bytes.fromhex(p["salt"]), p["n"], p["r"], p["p"]),
                                 bytes.fromhex(p["hash"]))
        with self.lock:
            if not ok:
                tries += 1
                if tries >= FREE_TRIES:
                    until = now + min(LOCK * 2 ** (tries - FREE_TRIES), 900.0)
                self.failures[name] = (tries, until)
                if until > now:
                    raise Locked(until - now)
                raise WrongPassphrase(FREE_TRIES - tries)
            self.failures.pop(name, None)
            token = secrets.token_urlsafe(32)
            self.sessions[token] = Session(name, now, now)
            return token

    def session(self, token: str | None) -> dict | None:
        """The profile a live session belongs to (and touch it), or None."""
        if not token:
            return None
        now = self.clock()
        with self.lock:
            s = self.sessions.get(token)
            if s is None:
                return None
            if now - s.seen > IDLE or now - s.created > LIFETIME:
                del self.sessions[token]
                return None
            s.seen = now
        return self.get(s.profile)

    def end(self, token: str | None) -> None:
        with self.lock:
            self.sessions.pop(token or "", None)
