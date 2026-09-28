"""The owner's watch as a second way in (docs/research/notes/G-watch-agent.md §8): pairing, finding this Mac,
and the LAN address.

A watch pairs once. It sends a six-digit code, which the owner reads off this Mac, and gets back a long random
token. Only the token's hash is kept. A code works once, lasts ten minutes and is burned after five wrong guesses.
Devices live in one JSON file, so `engram watch pair` / `forget` work while the server is running.

The Mac announces itself over mDNS (Bonjour) as `_engram._tcp`, so a watch finds it again when the hotspot hands
out a new address. Anyone on the network can announce that name, so a watch sends its token only to a server that
first proves it holds the token's hash: HMAC(token hash, the watch's random nonce)."""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import ipaddress
import json
import secrets
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

CODE_TTL = 600.0                        # seconds a pairing code stays valid
CODE_TRIES = 5                          # wrong guesses before the code is burned
SERVICE = "_engram._tcp"                # the mDNS service type the watch looks for


class Devices:
    """The paired watches: {"devices": [{name, token_sha256, paired_at}], "code": {sha256, expires, tries}}."""

    def __init__(self, path: Path):
        self.path = path

    def new_code(self) -> str:
        code = f"{secrets.randbelow(10**6):06d}"
        with self._locked():
            state = self._load()
            state["code"] = {"sha256": _sha256(code), "expires": time.time() + CODE_TTL, "tries": 0}
            self._save(state)
        return code

    def pair(self, code: str, name: str) -> str | None:
        """A new device token for the current code, or None (wrong, used, expired or burned code)."""
        with self._locked():
            state = self._load()
            c = state.get("code")
            if not c or c["expires"] < time.time():
                return None
            if not hmac.compare_digest(c["sha256"], _sha256(code.strip())):
                c["tries"] += 1
                if c["tries"] >= CODE_TRIES:
                    state["code"] = None
                self._save(state)
                return None
            token = secrets.token_urlsafe(32)
            name = (name.strip() or "watch")[:40]
            state["code"] = None
            state["devices"] = [d for d in state["devices"] if d["name"] != name] + [
                {"name": name, "token_sha256": _sha256(token), "paired_at": time.strftime("%Y-%m-%dT%H:%M:%S")}]
            self._save(state)
        return token

    def device(self, token: str) -> str | None:
        """The name of the device holding this token, or None."""
        h = _sha256(token)
        with self._locked():
            devices = self._load()["devices"]
        return next((d["name"] for d in devices if hmac.compare_digest(d["token_sha256"], h)), None)

    def proofs(self, nonce: str) -> list[str]:
        """HMAC-SHA256(token hash, nonce) for each paired device: a watch checks that one is its own before it sends
        its token, and learns nothing about anyone else's."""
        with self._locked():
            devices = self._load()["devices"]
        return [hmac.new(d["token_sha256"].encode(), nonce.encode(), hashlib.sha256).hexdigest() for d in devices]

    def list(self) -> list[dict]:
        with self._locked():
            return [{"name": d["name"], "paired_at": d["paired_at"]} for d in self._load()["devices"]]

    def forget(self, name: str) -> bool:
        with self._locked():
            state = self._load()
            kept = [d for d in state["devices"] if d["name"] != name]
            if len(kept) == len(state["devices"]):
                return False
            state["devices"] = kept
            self._save(state)
        return True

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """An OS file lock around each read-modify-write: the server and the CLI are separate processes."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path.with_suffix(".lock"), "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {"devices": [], "code": None}

    def _save(self, state: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=1))
        tmp.chmod(0o600)
        tmp.replace(self.path)


def lan_address(address: str = "auto") -> str:
    """This Mac's private IPv4 address on the local network: the one given, checked, or, for 'auto', the address of
    the interface the OS routes out of. The UDP connect sends no packet; it only picks the route."""
    if address == "auto":
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.connect(("10.254.254.254", 1))
            except OSError as e:
                raise ValueError("no network to find a LAN address on; pass one, e.g. --lan 192.168.1.20") from e
            address = s.getsockname()[0]
    ip = ipaddress.ip_address(address)
    if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_unspecified:
        raise ValueError(f"{address} is not a private LAN address (e.g. 192.168.x.x, 10.x.x.x)")
    return address


def advertise(port: int, name: str) -> subprocess.Popen | None:
    """Announce the watch listener over mDNS with macOS's own `dns-sd`, for as long as the returned process runs;
    None where there is no dns-sd (the watch then needs the address typed in)."""
    dns_sd = shutil.which("dns-sd")
    if dns_sd is None:
        return None
    return subprocess.Popen([dns_sd, "-R", name, SERVICE, "local", str(port), "path=/watch"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def private_peer(host: str) -> bool:
    """Whether a client address is not on the internet: Python's `is_private` (RFC 1918, unique local, loopback and
    reserved ranges) or link-local."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (ip.is_private or ip.is_link_local) and not ip.is_unspecified


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()
