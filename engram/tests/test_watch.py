"""The watch's way in: pairing, audio, routing speech, and the LAN listener's guards and endpoints."""
import hashlib
import hmac
import http.client
import io
import json
import threading
import time
import urllib.error
import urllib.request
import wave
from http.server import ThreadingHTTPServer

import numpy as np
import pytest

from engram import serve as srv
from engram.act import Tool
from engram.config import Settings
from engram.db import connect
from engram.judge import verify_ledger
from engram.serve import AgentRun, Brain, make_watch_handler
from engram.voice import route, samples
from engram.watch import CODE_TRIES, Devices, lan_address


def wav(seconds=1.0, rate=16_000, channels=1, width=2) -> bytes:
    n = int(seconds * rate)
    tone = (np.sin(np.arange(n) * 2 * np.pi * 440 / rate) * 12_000).astype("<i2")
    frames = np.repeat(tone, channels) if width == 2 else (tone // 256 + 128).astype(np.uint8)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(frames.tobytes())
    return buf.getvalue()


# ------------------------------------------------------------------------------------------------ pairing

def test_a_code_pairs_once_and_a_forgotten_watch_is_refused(tmp_path):
    devices = Devices(tmp_path / "watch.json")
    code = devices.new_code()
    token = devices.pair(code, "galaxy")
    assert token and devices.device(token) == "galaxy"
    assert devices.pair(code, "again") is None                              # one use
    assert (tmp_path / "watch.json").stat().st_mode & 0o777 == 0o600
    assert token not in (tmp_path / "watch.json").read_text()               # only its hash is kept
    assert devices.forget("galaxy") and devices.device(token) is None
    assert not devices.forget("galaxy")


def test_guessing_burns_the_code_and_old_codes_expire(tmp_path, monkeypatch):
    devices = Devices(tmp_path / "watch.json")
    code = devices.new_code()
    wrong = f"{(int(code) + 1) % 10**6:06d}"
    for _ in range(CODE_TRIES):
        assert devices.pair(wrong, "w") is None
    assert devices.pair(code, "w") is None                                  # burned: even the right code fails
    code = devices.new_code()
    monkeypatch.setattr("engram.watch.time.time", lambda: 1e12)
    assert devices.pair(code, "w") is None                                  # expired


def test_lan_address_must_be_private():
    assert lan_address("192.168.137.243") == "192.168.137.243"
    for bad in ("8.8.8.8", "127.0.0.1", "0.0.0.0", "fe80::1"):
        with pytest.raises(ValueError):
            lan_address(bad)


# ------------------------------------------------------------------------------------------------- speech

def test_samples_are_mono_float_at_16k():
    x = samples(wav(1.0))
    assert x.dtype == np.float32 and len(x) == 16_000 and 0.3 < np.abs(x).max() < 0.4
    assert len(samples(wav(0.5, rate=8_000, channels=2))) == 8_000          # resampled, channels averaged
    for bad in (wav(0.5, width=1), b"not audio"):
        with pytest.raises(ValueError):
            samples(bad)


@pytest.mark.parametrize(("heard", "expected"), [
    ("Remember that the board deck is due Friday.", ("add", "The board deck is due Friday.")),
    ("remember, call Stinson about the model", ("add", "Call Stinson about the model")),
    ("Take a note that Vince prefers mornings.", ("add", "Vince prefers mornings.")),
    ("Remember when Vince moved the meeting?", ("ask", "Remember when Vince moved the meeting?")),
    ("Remembering things is hard", ("ask", "Remembering things is hard")),
    ("Remember.", ("ask", "Remember.")),
    ("Who was Bernard Murphy's PhD supervisor?", ("ask", "Who was Bernard Murphy's PhD supervisor?")),
])
def test_route(heard, expected):
    assert route(heard) == expected


# -------------------------------------------------------------------------------------------- the listener

def call(base, path, token=None, body=None, headers=None, ctype="application/json"):
    h = {**({"Authorization": f"Bearer {token}"} if token else {}), **(headers or {})}
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        h["Content-Type"] = ctype
    req = urllib.request.Request(base + path, data=data, headers=h, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.fixture
def watch(tmp_path):
    brain = Brain(Settings(database_url="postgresql://unused/none", data_dir=tmp_path), workbench=False)
    devices = Devices(tmp_path / "watch.json")
    server = ThreadingHTTPServer(("127.0.0.1", 0), None)
    port = server.server_address[1]
    server.RequestHandlerClass = make_watch_handler(brain, devices)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield brain, devices, f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        brain.llm.close()


def test_listener_guards(watch):
    _, devices, base = watch
    assert call(base, "/watch/hello") == (200, {"engram": True})            # reachable before pairing
    assert call(base, "/watch/pending")[0] == 401                          # but nothing else
    assert call(base, "/watch/pair", body={"code": "000000"})[0] == 403
    token = call(base, "/watch/pair", body={"code": devices.new_code(), "name": "galaxy"})[1]["token"]
    assert call(base, "/watch/pending?wait=0", token)[0] == 200
    assert call(base, "/watch/pending", "wrong-token")[0] == 401
    assert call(base, "/watch/pending", token, headers={"Origin": "http://evil.example"})[0] == 403   # a browser
    assert call(base, "/watch/pending", token, headers={"Host": "evil.example"})[0] == 403           # rebinding
    for path in ("/api/sql", "/api/status", "/api/graph", "/api/ledger", "/"):                      # localhost only
        assert call(base, path, token)[0] == 404
    assert call(base, "/api/sql", token, body={"sql": "SELECT 1"})[0] == 404
    assert call(base, "/watch/ask", token, body={"question": "x"}, ctype="text/plain")[0] == 415
    assert call(base, "/watch/voice", token, body=wav(), ctype="application/json")[0] == 415        # WAV only
    host, port = base.removeprefix("http://").split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=10)     # refused on the declared size, unread
    conn.putrequest("POST", "/watch/voice")
    for k, v in {"Authorization": f"Bearer {token}", "Content-Type": "audio/wav",
                 "Content-Length": str(srv.MAX_AUDIO + 1)}.items():
        conn.putheader(k, v)
    conn.endheaders()
    assert conn.getresponse().status == 413
    conn.close()


def test_hello_proves_this_is_the_mac_the_watch_paired_with(watch):
    _, devices, base = watch
    token = devices.pair(devices.new_code(), "galaxy")
    status, r = call(base, "/watch/hello?nonce=abc123")                        # no token sent
    key = hashlib.sha256(token.encode()).hexdigest().encode()
    assert status == 200 and r["proofs"] == [hmac.new(key, b"abc123", hashlib.sha256).hexdigest()]
    assert "proofs" not in call(base, "/watch/hello?nonce=" + "a" * 65)[1]      # a bounded nonce only
    assert call(base, "/watch/hello", headers={"Host": f"localhost:{base.rsplit(':', 1)[1]}"})[0] == 403  # IPs only


def test_long_poll_wakes_on_a_new_approval_and_the_watch_decides(watch):
    brain, devices, base = watch
    token = devices.pair(devices.new_code(), "galaxy")
    first = call(base, "/watch/pending?wait=0", token)[1]
    assert first["pending"] == []
    run = AgentRun("email Stinson the model")
    brain.runs["r1"] = run

    def escalate():
        time.sleep(0.3)
        run.pending = {"tool": "send_email", "effect": "external", "preview": "email to stinson", "judge": None}
        brain._changed()

    threading.Thread(target=escalate).start()
    t0 = time.monotonic()
    status, got = call(base, f"/watch/pending?since={first['version']}&wait=10", token)
    assert status == 200 and time.monotonic() - t0 < 5                      # woke on the change, not the timeout
    assert got["pending"] == [{"run": "r1", "request": "email Stinson the model", "tool": "send_email",
                               "effect": "external", "preview": "email to stinson", "judge": None, "on_watch": True}]
    assert call(base, "/watch/decide", token, body={"run": "r1", "approve": True}) == (200, {"ok": True})
    assert run.decided.is_set() and run.approved and run.channel == "watch:galaxy"
    assert call(base, "/watch/decide", token, body={"run": "r1", "approve": False})[0] == 409     # decided once
    assert call(base, "/watch/decide", token, body={"run": "nope", "approve": True})[0] == 404

    brain.runs["r2"] = danger = AgentRun("delete everything")
    danger.pending = {"tool": "delete_all", "effect": "destructive", "preview": "delete all", "judge": None}
    assert [p["on_watch"] for p in call(base, "/watch/pending?wait=0", token)[1]["pending"]] == [True, False]
    assert call(base, "/watch/decide", token, body={"run": "r2", "approve": True})[0] == 403      # laptop only
    assert not danger.decided.is_set()
    assert brain.decide("r2", False, "page") == {"ok": True}                                      # the page can


def test_voice_routes_to_add_or_ask(watch, monkeypatch):
    brain, devices, base = watch
    token = devices.pair(devices.new_code(), "galaxy")
    heard = iter(["Remember that the deck is due Friday.", "When is the deck due?", ""])
    brain.transcribe = lambda audio: next(heard)
    added, asked = [], []
    monkeypatch.setattr(brain, "add", lambda body: added.append(body) or {"id": "a1"})
    monkeypatch.setattr(brain, "ask", lambda body: asked.append(body) or {
        "answer": "Friday [3].", "answered_by": "S2", "seconds": 2.1, "touched": {}, "kept": 1, "considered": 9,
        "cites": [{"item": 3, "date": "2001-01-05", "from": "a@b", "subject": "Deck", "snippet": "…"}]})
    status, r = call(base, "/watch/voice", token, body=wav(), ctype="audio/wav")
    assert status == 200 and r["kind"] == "add" and r["id"] == "a1"
    assert added == [{"text": "The deck is due Friday.", "title": "Voice note", "remember": True}]
    status, r = call(base, "/watch/voice", token, body=wav(), ctype="audio/wav")
    assert status == 200 and asked == [{"question": "When is the deck due?"}]
    assert r == {"heard": "When is the deck due?", "kind": "ask", "heard_ms": r["heard_ms"], "answer": "Friday [3].",
                 "answered_by": "S2", "seconds": 2.1, "cites": ["2001-01-05 Deck"]}
    assert call(base, "/watch/voice", token, body=wav(), ctype="audio/wav")[0] == 422             # heard nothing
    assert call(base, "/watch/voice", token, body=wav(0.1), ctype="audio/wav")[0] == 422          # too short


def test_voice_without_speech_recognition_says_so(watch):
    brain, devices, base = watch
    token = devices.pair(devices.new_code(), "galaxy")
    brain.transcribe.model = "mlx-community/not-downloaded"
    status, r = call(base, "/watch/voice", token, body=wav(), ctype="audio/wav")
    assert status == 503 and ("not installed" in r["error"] or "not downloaded" in r["error"])


# ------------------------------------------------------------------------------------------ the ledger

@pytest.mark.db
def test_an_approval_through_the_gate_is_decided_on_the_watch_and_ledgered(db_url, tmp_path, monkeypatch):
    """The real approve path in Brain._act: the gate escalates, the watch hears of it, approves, the tool runs,
    and the owner's decision lands in the hash-chained ledger."""
    ran = []
    tool = Tool("send_email", "external", lambda **a: ran.append(a) or "sent", preview=lambda a: "email to stinson")

    def fake_run(llm, model, system, request, tools, gate, subject, on_step=None):
        if gate.approve(request, tool, {"to": "stinson"}, None):
            tool.run(to="stinson")
        return type("R", (), {"answer": "done"})()

    monkeypatch.setattr(srv.agent, "run", fake_run)
    monkeypatch.setattr(srv.wb, "tools", lambda domains: [tool])
    brain = Brain(Settings(database_url=db_url, data_dir=tmp_path), workbench=True)
    try:
        version = brain.pending()["version"]
        run_id = brain.act({"request": "email Stinson"})["id"]
        pending = brain.pending(version, wait=10)["pending"]
        assert [p["run"] for p in pending] == [run_id]
        brain.decide(run_id, True, "watch:galaxy")
        for _ in range(100):
            if brain.runs[run_id].status == "done":
                break
            time.sleep(0.05)
        assert brain.run_state(run_id)["status"] == "done" and ran == [{"to": "stinson"}]
        with connect(db_url) as conn:
            row = conn.execute("SELECT question, subject, tier, model, value FROM judgements "
                               "ORDER BY id DESC LIMIT 1").fetchone()
            assert row == {"question": "approve", "subject": f"act:{run_id}", "tier": "H",
                           "model": "owner:watch:galaxy", "value": "yes"}
            assert verify_ledger(conn) is None

        monkeypatch.setattr(srv, "APPROVAL_WAIT", 0.2)                   # nobody answers: it counts as "no"
        ran.clear()
        run_id = brain.act({"request": "email Stinson"})["id"]
        for _ in range(100):
            if brain.runs[run_id].status == "done":
                break
            time.sleep(0.05)
        assert ran == [] and brain.runs[run_id].channel == "timeout"
        with pytest.raises(LookupError):
            brain.decide(run_id, True, "watch:galaxy")                  # too late: not a false "ok"
        with connect(db_url) as conn:
            row = conn.execute("SELECT model, value FROM judgements ORDER BY id DESC LIMIT 1").fetchone()
            assert row == {"model": "owner:timeout", "value": "no"} and verify_ledger(conn) is None
    finally:
        brain.llm.close()
