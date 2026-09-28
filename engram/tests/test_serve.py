"""The local page's server: endpoints that need no model, sign-in, the guards against other origins and host names,
and profile isolation (a session for one brain never reaches another's database)."""
import json
import threading
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from http.server import ThreadingHTTPServer

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from engram.config import Settings
from engram.judge import Answer, append
from engram.profiles import Profiles
from engram.serve import Brains, make_handler

pytestmark = pytest.mark.db
JS = {"Content-Type": "application/json"}


def fetch(url, headers=None, body=None):
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


@contextmanager
def server(db_url, tmp_path):
    settings = Settings(database_url=db_url, data_dir=tmp_path)
    brains, profiles = Brains(settings, workbench=False), Profiles(tmp_path / "profiles.json")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), None)
    port = srv.server_address[1]
    srv.RequestHandlerClass = make_handler(brains, {f"127.0.0.1:{port}", f"localhost:{port}"}, profiles)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}", profiles, brains
    finally:
        srv.shutdown()
        srv.server_close()
        brains.close()


def login(base, name, passphrase):
    status, headers, body = fetch(base + "/api/login", JS, json.dumps({"profile": name, "passphrase": passphrase})
                                  .encode())
    assert status == 200, body
    cookie = headers["Set-Cookie"]
    return {"Cookie": cookie.split(";")[0]}, cookie


def test_page_endpoints_and_guards(db_url, tmp_path):
    database = conninfo_to_dict(db_url)["dbname"]
    with server(db_url, tmp_path) as (base, profiles, _):
        profiles.add("owner", "correct horse", database)
        status, headers, page = fetch(base + "/")
        assert status == 200 and b"<title>engram</title>" in page
        assert "script-src 'self'" in headers["Content-Security-Policy"]
        assert fetch(base + "/api/status")[0] == 401                                           # signed out
        auth, cookie = login(base, "owner", "correct horse")
        assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/" in cookie
        get = lambda path, h=None: fetch(base + path, {**auth, **(h or {})})                   # noqa: E731
        status, _, body = get("/api/status")
        assert status == 200 and json.loads(body)["items"] == 0 and json.loads(body)["brain"] == database
        assert json.loads(get("/api/ledger?verify=1")[2])["intact"]
        assert json.loads(get("/api/beliefs")[2]) == []
        assert get("/api/item/1")[0] == 404
        assert get("/api/status", {"Origin": "http://evil.example"})[0] == 403                 # cross-site
        assert get("/api/status", {"Host": "evil.example"})[0] == 403                         # DNS rebinding
        post = lambda path, body, h=JS: fetch(base + path, {**auth, **h}, body)                # noqa: E731
        assert post("/api/act", b'{"request": "x"}', {"Content-Type": "text/plain"})[0] == 415
        status, _, body = post("/api/act", b'{"request": "x"}')
        assert status == 409 and b"WorkBench" in body                                          # no sandbox here
        graph = json.loads(get("/api/graph")[2])
        assert [n["id"] for n in graph["nodes"]] == ["owner"] and graph["links"] == []
        ok = json.loads(post("/api/sql", b'{"sql": "SELECT 1 + 1 AS two"}')[2])
        assert ok["columns"] == ["two"] and ok["rows"] == [[2]]
        assert post("/api/sql", b'{"sql": "DELETE FROM items"}')[0] == 400                     # read-only
        assert post("/api/sql", b'{"sql": "SELECT 1; SELECT 2"}')[0] == 400                    # one statement
        for attack in ("COPY (SELECT 1) TO PROGRAM 'true'", "SELECT pg_read_file('/etc/hosts')",
                       "SELECT set_config('role', 'engram', false), pg_read_file('/etc/hosts')"):
            assert post("/api/sql", json.dumps({"sql": attack}).encode())[0] == 400            # not a superuser
        for asset in ("/vendor/3d-force-graph.min.js", "/app.js", "/styles/base.css", "/vendor/fonts/"
                      "InstrumentSans-600.woff2"):
            assert fetch(base + asset)[0] == 200, asset
        for escape in ("/vendor/../../serve.py", "/vendor/%2e%2e/%2e%2e/serve.py", "/../profiles.py",
                       "/../../data/profiles.json"):
            assert fetch(base + escape)[0] == 404                                            # no path escape
        assert fetch(base + "/api/logout", {**auth, **JS}, b"{}")[0] == 200
        assert get("/api/status")[0] == 401                                                   # the session is gone


def test_login_is_rate_limited_and_says_so(db_url, tmp_path):
    database = conninfo_to_dict(db_url)["dbname"]
    with server(db_url, tmp_path) as (base, profiles, _):
        profiles.add("owner", "correct horse", database)
        bad = json.dumps({"profile": "owner", "passphrase": "wrong horse"}).encode()
        status, _, body = fetch(base + "/api/login", JS, bad)
        assert status == 401 and json.loads(body)["remaining"] == 4 and "Set-Cookie" not in _
        for _ in range(3):
            fetch(base + "/api/login", JS, bad)
        status, _, body = fetch(base + "/api/login", JS, bad)
        assert status == 429 and json.loads(body)["retry_after"] > 0
        right = json.dumps({"profile": "owner", "passphrase": "correct horse"}).encode()
        assert fetch(base + "/api/login", JS, right)[0] == 429                               # locked even when right
        assert fetch(base + "/api/login", {"Content-Type": "text/plain"}, right)[0] == 415
        assert fetch(base + "/api/login", {**JS, "Origin": "http://evil.example"}, right)[0] == 403
        assert fetch(base + "/api/login", JS, json.dumps({"profile": "nobody", "passphrase": "x"}).encode())[0] == 404


def test_profiles_are_isolated(db_url, tmp_path):
    """Two brains made from the page: each session sees only its own database, whatever the request says."""
    made = []
    with server(db_url, tmp_path) as (base, _, _):
        cookies = {}
        for name in (f"a{uuid.uuid4().hex[:8]}", f"b{uuid.uuid4().hex[:8]}"):
            status, headers, body = fetch(base + "/api/profiles", JS, json.dumps(
                {"name": name, "passphrase": f"{name} secret", "color": "s2"}).encode())
            assert status == 200, body
            made.append(name)
            cookies[name] = {"Cookie": headers["Set-Cookie"].split(";")[0]}
        a, b = made
        with psycopg.connect(make_conninfo(db_url, dbname=b)) as conn:                      # something only B has
            conn.execute("INSERT INTO items (source, kind, content_hash, body, direction) VALUES "
                         "('test', 'note', 'h1', 'only in b', 'in')")
        for who, items in ((a, 0), (b, 1)):
            st = json.loads(fetch(base + f"/api/status?database={a if who == b else b}", cookies[who])[2])
            assert st["brain"] == who and st["items"] == items                               # its own, never the other
            schema = json.loads(fetch(base + "/api/schema", cookies[who])[2])
            assert next(t for t in schema["tables"] if t["name"] == "items")["rows"] == items
            sample = json.loads(fetch(base + "/api/schema/items", cookies[who])[2])["sample"]
            assert len(sample["rows"]) == items
            q = json.dumps({"sql": "SELECT current_database() AS db, count(*) AS n FROM items"}).encode()
            assert json.loads(fetch(base + "/api/sql", {**cookies[who], **JS}, q)[2])["rows"] == [[who, items]]
            agents = json.loads(fetch(base + "/api/agents", cookies[who])[2])
            assert {x["id"] for x in agents} >= {"parser", "judge", "ask", "owner", "watch"}
        tiles = {t["name"]: t for t in json.loads(fetch(base + "/api/profiles")[2])["profiles"]}
        assert tiles[a]["counts"]["items"] == 0 and tiles[b]["counts"]["items"] == 1
        assert "database" not in tiles[a] and all(set(n) == {"id", "kind"} for n in tiles[b]["graph"]["nodes"])
        assert fetch(base + "/api/status", {"Cookie": "engram_session=forged"})[0] == 401
        # the page never adopts an existing database, or re-registers a name
        for name, code in ((conninfo_to_dict(db_url)["dbname"], 409), (a, 409), ("postgres", 400), ("Bad!", 400)):
            status, _, _ = fetch(base + "/api/profiles", JS, json.dumps({"name": name, "passphrase": "long enough"})
                                 .encode())
            assert status == code, name
    with psycopg.connect(make_conninfo(db_url, dbname="postgres"), autocommit=True) as conn:
        for name in made:
            conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


def test_ledger_pages_filters_and_names_agents(db_url, tmp_path):
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as conn:
        for i in range(30):
            tier = ("S1", "S2", "H")[i % 3]
            model = {"S1": "qwen3:1.7b", "S2": "qwen3:14b", "H": "owner:watch:SM-R905F"}[tier]
            append(conn, "remember" if i % 2 else "relevant", f"item:{i}", f"h{i}",
                   Answer(tier, model, {}, {"yes": 0.9, "no": 0.1}, "yes", True, 10.0 + i))
    database = conninfo_to_dict(db_url)["dbname"]
    with server(db_url, tmp_path) as (base, profiles, _):
        profiles.add("owner", "correct horse", database)
        auth, _ = login(base, "owner", "correct horse")
        page = json.loads(fetch(base + "/api/ledger?limit=10", auth)[2])
        ids = [r["id"] for r in page["rows"]]
        assert len(ids) == 10 and ids == sorted(ids, reverse=True) and page["last_id"] == ids[0]
        older = json.loads(fetch(base + f"/api/ledger?limit=10&before_id={ids[-1]}", auth)[2])["rows"]
        assert older[0]["id"] == ids[-1] - 1
        newer = json.loads(fetch(base + f"/api/ledger?after_id={ids[1]}", auth)[2])["rows"]
        assert [r["id"] for r in newer] == [ids[0]]
        watch = json.loads(fetch(base + "/api/ledger?actor=owner:watch", auth)[2])["rows"]
        assert watch and all(r["tier"] == "H" and r["agent"] == "watch" for r in watch)
        s1 = json.loads(fetch(base + "/api/ledger?tier=S1&question=remember", auth)[2])["rows"]
        assert s1 and all(r["agent"] == "memgate" and r["entry"] == "parser" for r in s1)
        assert all(len(r["hash"]) == 12 and len(r["prev"]) == 12 for r in s1)
        drawer = json.loads(fetch(base + "/api/agents/memgate", auth)[2])
        assert drawer["decisions"] and drawer["p50"] is not None and len(drawer["latencies"]) <= 60
        assert fetch(base + "/api/agents/nobody", auth)[0] == 404
        assert json.loads(fetch(base + "/api/ledger/questions", auth)[2]) == ["relevant", "remember"]


def test_roles_the_day_plan_and_heralds_cards(db_url, tmp_path):
    with psycopg.connect(db_url, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("TRUNCATE herald_cards, plan_entries RESTART IDENTITY")
        for question, subject, tier in (("contradicts", "belief:1|belief:2", "S1"), ("todo", "belief:3", "S1"),
                                        ("supported", "item:4|ask:q", "S1"), ("intent", "meeting:ab12", "S2"),
                                        ("contradicts", "belief:1|belief:2", "S2")):
            append(conn, question, subject, "h", Answer(tier, "m", {}, {"yes": 1.0}, "yes", True, 5.0))
        for version, title in ((1, "Draft the memo"), (2, "Send the memo")):
            conn.execute("INSERT INTO plan_entries (day, version, title, starts, ends, kind) VALUES ('2000-10-30', "
                         "%s, %s, '2000-10-30 15:00+00', '2000-10-30 15:30+00', 'task')", (version, title))
        card = conn.execute("INSERT INTO herald_cards (role, kind, subject, title, body, actions, route, why) VALUES "
                            "('memory', 'due', 'belief:9:due', 'Due in 40 min', 'Send the deck', "
                            "'[{\"id\": \"done\", \"label\": \"Done\"}, {\"id\": \"snooze\", \"label\": \"Snooze\"}]',"
                            " 'now', 'due soon') RETURNING id").fetchone()["id"]
        conn.commit()
    database = conninfo_to_dict(db_url)["dbname"]
    with server(db_url, tmp_path) as (base, profiles, _):
        profiles.add("owner", "correct horse", database)
        auth, _ = login(base, "owner", "correct horse")
        agents = json.loads(fetch(base + "/api/agents", auth)[2])
        assert {a["role"] for a in agents} >= {"Librarian", "Researcher", "Memory", "Planner", "Operator", "Guardian",
                                               "Herald", "Diplomat"}
        rows = {(r["question"], r["tier"]): r for r in json.loads(fetch(base + "/api/ledger", auth)[2])["rows"]}
        assert (rows["contradicts", "S1"]["agent"], rows["contradicts", "S2"]["agent"]) == ("memcheck", "second")
        assert (rows["todo", "S1"]["agent"], rows["todo", "S1"]["entry"]) == ("todo", "planner")
        assert rows["supported", "S1"]["agent"] == "support"
        assert (rows["intent", "S2"]["agent"], rows["intent", "S2"]["entry"]) == ("intent", "gate")
        plan = json.loads(fetch(base + "/api/plan", auth)[2])               # the latest day and its latest version
        assert (plan["day"], plan["version"], [e["title"] for e in plan["entries"]]) == \
            ("2000-10-30", 2, ["Send the memo"])
        assert plan["entries"][0]["starts"] == "09:00"                       # 15:00 UTC in Chicago (CST by then)
        assert [c["id"] for c in json.loads(fetch(base + "/api/herald", auth)[2])] == [card]
        tap = lambda action: fetch(base + f"/api/herald/{card}", {**auth, **JS},     # noqa: E731
                                   json.dumps({"action": action}).encode())
        assert tap("delete")[0] == 400                                       # not an answer this card offers
        assert json.loads(tap("snooze")[2])["snoozed_until"]
        assert json.loads(fetch(base + "/api/herald", auth)[2]) == []        # snoozed: out of sight for now
        assert fetch(base + "/api/plan", JS, b"{}")[0] == 401                # every role's route needs a session
