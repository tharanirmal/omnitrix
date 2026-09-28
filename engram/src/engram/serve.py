"""A local web page for the brain: ask, search, memory, the gated agent (the owner approves in the page) and the
ledger. Standard library only, bound to 127.0.0.1, and the page loads nothing from the network. Requests from other
origins or host names are refused, so no other web page can drive the agent (CSRF, DNS rebinding).

Every brain is a profile (profiles.py): its own Postgres database, opened with a passphrase. The page signs in with
an HttpOnly, SameSite=Strict session cookie and every /api/* call works on the database of the signed-in profile only;
Brain objects are cached per database. The page is a set of small ES modules and stylesheets under web/, served from
here with a Content-Security-Policy that allows only this origin.

With `--lan`, a second listener serves the owner's paired watch on the local network. It is a separate handler with
its own short allow-list: approvals, asking, adding and voice. It needs a device token and refuses browsers, and it
serves the brain `engram serve` was started with. The SQL console, graph, ledger and page stay on 127.0.0.1
(docs/research/notes/G-watch-agent.md §8)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import psycopg
from psycopg import sql as pgsql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from . import agent, herald, index
from .act import Gate, Tool, describe
from .ask import ask
from .config import Settings
from .db import connect, migrate
from .judge import Answer, Judge, OllamaScorer, Verdict, append, make_scorer, verify_ledger
from .llm import Ollama
from .profiles import COOKIE, Locked, Profiles, WrongPassphrase
from .sources import workbench as wb
from .voice import Transcriber, Unavailable, route, samples
from .watch import Devices, advertise, private_peer

WEB = Path(__file__).parent / "web"
PAGE = WEB / "index.html"
LABEL_PAGE = WEB / "label.html"
STATIC = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".woff2": "font/woff2",
          ".svg": "image/svg+xml", ".md": "text/markdown; charset=utf-8"}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self'; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'none'")
MEMORY_QUESTIONS = ["remember", "meeting_request", "same_belief", "fulfilled", "contradicts", "todo"]
STAGES = ["stored", "embedded", "gate", "extracted", "vault"]
APPROVAL_WAIT = 600.0                   # seconds a pending action waits for the owner before counting as "no"
LONG_POLL = 25.0                        # longest a watch's wait for a change in pending approvals is held open
MAX_JSON, MAX_AUDIO = 64 << 10, 4 << 20 # request bodies from the watch: ~2 min of 16 kHz mono audio at most


@dataclass
class AddRun:
    title: str
    stages: list[dict] = field(default_factory=list)       # {stage, ms, detail}
    status: str = "running"                                 # running | done | error
    item: int | None = None
    beliefs: list[dict] = field(default_factory=list)
    error: str = ""


@dataclass
class AgentRun:
    request: str
    steps: list[dict] = field(default_factory=list)
    pending: dict | None = None         # the call waiting for the owner, with its preview and the judge's view
    status: str = "running"             # running | waiting | done | error
    answer: str = ""
    decided: threading.Event = field(default_factory=threading.Event)
    approved: bool = False
    channel: str = ""                   # where the owner decided: 'page' or 'watch:<device>'
    kind: str = "act"                   # act (the Operator's task) | meeting (Feature 2) | diplomat


class Brain:
    """What the handlers share. The small judge runs in-process (MLX), so asking is one at a time."""

    def __init__(self, settings: Settings, workbench: bool):
        self.settings, self.workbench = settings, workbench
        self.llm = Ollama(settings.ollama_url)
        self.worker = ThreadPoolExecutor(max_workers=1)     # MLX binds a model to the thread that loaded it: all
                                                            # in-process model work (asking, adding) runs here
        self.runs: dict[str, AgentRun] = {}
        self.adds: dict[str, AddRun] = {}
        self._judge: Judge | None = None
        self.changes = threading.Condition()                # approvals or Herald's cards changed: wakes the watch
        self.version = 0
        self.transcribe = Transcriber(settings.asr_model)
        self.booked: list = []                              # meetings accepted here: each run's WorkBench sandbox
                                                            # is fresh, so the next run's Planner is told of them
        self.asking = 0                                     # questions being answered right now
        self.planning = 0                                   # day plans being solved right now
        self.watch_seen: dict[str, float] = {}              # paired watch -> when it last reached us (time.time())
        self.lan = False                                    # whether the watch's listener is up
        self._models: tuple[float, dict | None] = (0.0, None)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.llm.embed(self.settings.embed_model, texts)

    def judge(self) -> Judge:
        if self._judge is None:
            s = self.settings
            self._judge = Judge(s.database_url, make_scorer(s.judge_model or s.s1_model, s.ollama_url),
                                OllamaScorer(s.ollama_url, s.s2_model))
        return self._judge

    # ---------------------------------------------------------------------------------------------- reading

    def status(self) -> dict:
        with connect(self.settings.database_url) as conn:
            row = conn.execute(
                "SELECT current_database() AS brain, (SELECT count(*) FROM items) AS items, "
                "(SELECT count(*) FROM chunks) AS chunks, (SELECT count(*) FROM current_beliefs) AS beliefs, "
                "(SELECT count(*) FROM judgements) AS judgements").fetchone()
        s = self.settings
        return {**row, "s1": s.judge_model or s.s1_model, "s2": s.s2_model, "workbench": self.workbench}

    # ------------------------------------------------------------------------------ the team's label checks

    def label_next(self, q: dict[str, str]) -> dict:
        from . import derive

        with connect(self.settings.database_url) as conn:
            return {"example": derive.next_to_check(conn, q.get("question", "remember")),
                    "progress": derive.agreement(conn)}

    def label(self, body: dict) -> dict:
        from . import derive

        with connect(self.settings.database_url) as conn:
            derive.check(conn, str(body.get("question", "")), str(body.get("subject", "")),
                         str(body.get("value", "")))
        return {"ok": True}

    def search(self, q: dict[str, str]) -> list[dict]:
        with connect(self.settings.database_url) as conn:
            hits = index.search(conn, self.embed, q["q"], int(q.get("k", 10)), since=_day(q.get("since")),
                                until=_day(q.get("until")), people=[q["person"]] if q.get("person") else ())
        return [{"item": h.item_id, "date": _date(h.sent_at), "from": h.from_addr, "subject": h.subject,
                 "text": h.text[:400], "why": h.why} for h in hits]

    def ask(self, body: dict) -> dict:
        self.asking += 1
        try:
            return self.worker.submit(self._ask, body).result()
        finally:
            self.asking -= 1

    def _ask(self, body: dict) -> dict:
        t0 = datetime.now()
        with connect(self.settings.database_url) as conn:
            r = ask(conn, self.judge(), self.llm, self.settings.s2_model, self.embed, body["question"],
                    people=[body["person"]] if body.get("person") else (), draft=self.settings.draft_model)
            cited = conn.execute("SELECT id, sent_at, from_addr, subject, left(body, 300) AS snippet FROM items "
                                 "WHERE id = ANY(%s)", (list(r.cites),)).fetchall()
        return {"answer": r.answer, "answered_by": r.answered_by, "verdict": _verdict(r.support), "kept": len(r.kept),
                "considered": len(r.considered), "seconds": round((datetime.now() - t0).total_seconds(), 1),
                "touched": {"considered": list(r.considered), "kept": list(r.kept), "cited": list(r.cites)},
                "cites": [{"item": c["id"], "date": _date(c["sent_at"]), "from": c["from_addr"],
                           "subject": c["subject"], "snippet": c["snippet"]} for c in cited]}

    def item(self, item_id: int) -> dict | None:
        with connect(self.settings.database_url) as conn:
            r = conn.execute("SELECT id, kind, sent_at, from_addr, to_addrs, subject, body, left(quoted, 3000) AS "
                             "quoted FROM items WHERE id = %s", (item_id,)).fetchone()
        return None if r is None else {**r, "sent_at": _date(r["sent_at"])}

    def beliefs(self, q: dict[str, str]) -> list[dict]:
        with connect(self.settings.database_url) as conn:
            rows = conn.execute(
                "SELECT id, kind, actor, other, statement, when_text, due_at, confidence, sent_at, item_id, quote, "
                "supersedes FROM current_beliefs WHERE (%(kind)s::text IS NULL OR kind = %(kind)s) "
                "AND (%(p)s::text IS NULL OR actor LIKE %(p)s OR other LIKE %(p)s) "
                "ORDER BY sent_at DESC NULLS LAST, id DESC LIMIT %(k)s",
                {"kind": q.get("kind") or None, "p": f"%{q['person'].lower()}%" if q.get("person") else None,
                 "k": int(q.get("k", 100))}).fetchall()
        return [{**r, "sent_at": _date(r["sent_at"]), "due_at": r["due_at"].isoformat() if r["due_at"] else None}
                for r in rows]

    def ledger(self, q: dict[str, str]) -> dict:
        """Judgements, newest first, with keyset paging (`before_id` for older rows, `after_id` for new ones) and
        filters: tier (comma-separated), question, actor (a part of the model name, e.g. owner:watch), since/until
        (dates). `verify=1` checks the whole hash chain instead."""
        with connect(self.settings.database_url) as conn:
            if q.get("verify"):
                bad = verify_ledger(conn)
                n = conn.execute("SELECT count(*) AS n FROM judgements").fetchone()["n"]
                return {"intact": bad is None, "first_bad": bad, "judgements": n}
            where, args = ["TRUE"], {"limit": max(1, min(int(q.get("limit", 50)), 200))}
            if q.get("before_id", "").isdigit():
                where.append("id < %(before)s")
                args["before"] = int(q["before_id"])
            if q.get("after_id", "").isdigit():
                where.append("id > %(after)s")
                args["after"] = int(q["after_id"])
            if q.get("tier"):
                where.append("tier = ANY(%(tiers)s)")
                args["tiers"] = [t for t in q["tier"].split(",") if t in ("S1", "S2", "H")]
            if q.get("question"):
                where.append("question = %(question)s")
                args["question"] = q["question"]
            if q.get("actor"):
                where.append("model ILIKE %(actor)s")
                args["actor"] = "%" + q["actor"].replace("%", "").replace("_", "\\_") + "%"
            if q.get("since"):
                where.append("created_at >= %(since)s")
                args["since"] = _day(q["since"])
            if q.get("until"):
                where.append("created_at < %(until)s + interval '1 day'")
                args["until"] = _day(q["until"])
            rows = conn.execute("SELECT id, created_at, question, subject, tier, model, value, probs, settled, "
                                "latency_ms, left(hash, 12) AS hash, left(prev_hash, 12) AS prev FROM judgements "
                                f"WHERE {' AND '.join(where)} ORDER BY id DESC LIMIT %(limit)s", args).fetchall()
            last = conn.execute("SELECT max(id) AS id FROM judgements").fetchone()["id"]
        return {"last_id": last, "rows": [
            {**{k: v for k, v in r.items() if k != "probs"},
             "created_at": r["created_at"].isoformat(timespec="seconds"),
             "p": round(r["probs"].get(r["value"], 0.0), 3) if r["value"] else None,
             "agent": agent_for(r), "entry": entry_for(r)} for r in rows]}

    def questions(self) -> list[str]:
        with connect(self.settings.database_url) as conn:
            return [r["question"] for r in conn.execute("SELECT DISTINCT question FROM judgements ORDER BY 1")]

    def graph(self) -> dict:
        """The brain as a graph: the owner, their main correspondents, recent and belief-bearing items, current
        beliefs. Bounded (a few hundred nodes) so it stays legible and fast."""
        with connect(self.settings.database_url) as conn:
            people = [r["addr"] for r in conn.execute(
                "SELECT addr FROM (SELECT from_addr AS addr FROM items WHERE direction = 'in' UNION ALL "
                "SELECT unnest(to_addrs) FROM items WHERE direction = 'out') t WHERE addr LIKE '%%@%%' "
                "GROUP BY addr ORDER BY count(*) DESC LIMIT 40")]
            beliefs = conn.execute("SELECT id, kind, actor, other, statement, item_id, author, status FROM "
                                   "current_beliefs ORDER BY id DESC LIMIT 300").fetchall()
            items = conn.execute(
                "(SELECT id, kind, subject, from_addr, to_addrs, sent_at, direction FROM items "
                " WHERE id = ANY(%(b)s)) UNION (SELECT id, kind, subject, from_addr, to_addrs, sent_at, direction "
                " FROM items WHERE (from_addr = ANY(%(p)s) OR to_addrs && %(p)s) ORDER BY sent_at DESC NULLS LAST "
                " LIMIT 160)", {"b": [b["item_id"] for b in beliefs], "p": people}).fetchall()
        return _graph(people, items, beliefs)

    def item_node(self, item_id: int) -> dict | None:
        """One item as graph nodes and links, for things a query or an upload brings into view."""
        with connect(self.settings.database_url) as conn:
            it = conn.execute("SELECT id, kind, subject, from_addr, to_addrs, sent_at, direction FROM items "
                              "WHERE id = %s", (item_id,)).fetchone()
            beliefs = conn.execute("SELECT id, kind, actor, other, statement, item_id, author, status FROM "
                                   "current_beliefs WHERE item_id = %s", (item_id,)).fetchall()
        return None if it is None else _graph([], [it], beliefs, people_from_items=True)

    def sql(self, body: dict) -> dict:
        """A read-only query: one statement, a read-only transaction, a 3 s timeout, at most 500 rows."""
        statement = body.get("sql", "").strip().rstrip(";")
        if not statement or ";" in statement:
            raise ValueError("one statement, please")
        t0 = datetime.now()
        reader = make_conninfo(self.settings.database_url, user="engram_reader", password="engram_reader")
        with connect(reader) as conn:                       # a role that can only read (sql/009_reader.sql)
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '3s'")
            cur = conn.execute(statement)
            cols = [d.name for d in cur.description or []]
            rows = cur.fetchmany(500)
            conn.rollback()
        return {"columns": cols, "rows": [[_cell(r[c]) for c in cols] for r in rows],
                "ms": round((datetime.now() - t0).total_seconds() * 1000, 1)}

    # ---------------------------------------------------------------------------------- the dashboard's views

    def counts(self) -> dict:
        with connect(self.settings.database_url) as conn:
            return conn.execute("SELECT (SELECT count(*) FROM items) AS items, (SELECT count(*) FROM current_beliefs) "
                                "AS beliefs, (SELECT count(*) FROM judgements) AS judgements").fetchone()

    def sample(self, n: int = 60) -> dict:
        """The shape of this brain's graph for its login tile: kinds and links only, no names or text."""
        g = self.graph()
        keep = [x for x in g["nodes"] if x["type"] != "item"][: n // 2]
        keep += [x for x in g["nodes"] if x["type"] == "item"][: n - len(keep)]
        ids = {x["id"]: i for i, x in enumerate(keep)}
        kind = {"owner": "person", "person": "person", "item": "item"}
        return {"nodes": [{"id": ids[x["id"]], "kind": kind.get(x["type"]) or x.get("kind", "item")} for x in keep],
                "links": [[ids[link["source"]], ids[link["target"]]] for link in g["links"]
                          if link["source"] in ids and link["target"] in ids]}

    def _model_state(self) -> dict | None:
        """The models Ollama has ({name: loaded?}), or None when it cannot be reached. Cached for 5 s."""
        at, models = self._models
        if time.monotonic() - at < 5:
            return models
        try:
            with httpx.Client(base_url=self.settings.ollama_url, timeout=0.5) as c:
                have = {m["name"] for m in c.get("/api/tags").json().get("models", [])}
                loaded = {m["name"] for m in c.get("/api/ps").json().get("models", [])}
            models = {name: name in loaded for name in have}
        except (httpx.HTTPError, ValueError):
            models = None
        self._models = (time.monotonic(), models)
        return models

    def _available(self, model: str) -> bool:
        if model.startswith("mlx:"):
            return importlib.util.find_spec("mlx_lm") is not None
        models = self._model_state()
        return models is not None and (model in models or f"{model}:latest" in models)

    def agents(self) -> list[dict]:
        """Every agent and component, with a status read from real state: the runs in flight, the watch's last
        visit, what Ollama has, and the ledger (p50/p95 over the last 200 rows, decisions today)."""
        s, now = self.settings, time.time()
        s1, s2 = s.judge_model or s.s1_model, s.s2_model
        adds = [r for r in list(self.adds.values()) if r.status == "running"]
        at = {STAGES[min(len(r.stages), len(STAGES) - 1)] for r in adds}          # the stage each add is on now
        runs = list(self.runs.values())
        waiting = sum(1 for r in runs if r.pending is not None)
        live = {k: any(r.kind == k and r.status in ("running", "waiting") for r in runs)
                for k in ("act", "meeting", "diplomat")}
        acting = any(live.values())
        ok1, ok2 = self._available(s1), self._available(s2)
        devices = Devices(s.watch_file).list()
        seen = max(self.watch_seen.values(), default=None)
        watch_name = devices[0]["name"] if devices else "watch"
        try:
            open_cards = len(self.cards())
        except Exception:                           # no herald_cards table yet (a brain not migrated): no cards
            open_cards = 0

        def st(running: bool, available: bool = True, wait: bool = False) -> str:
            return "offline" if not available else "waiting" if wait else "running" if running else "idle"

        def card(id_: str, name: str, tier: str, role: str | None, model: str, status: str, task: str = "",
                 **extra: Any) -> dict:
            return {"id": id_, "name": name, "tier": tier, "role": role, "model": model, "status": status,
                    "task": task, **extra}

        # the roster's roles (docs/research/agent-roster-review.md §2) as named cards on the tier that does the work
        out = [
            card("parser", "parser · dedupe", "S0", "Librarian", "text.py · store.py",
                 st(bool(at & {"stored", "embedded"})),
                 "splitting and embedding a new item" if at & {"stored", "embedded"} else ""),
            card("vault", "vault sync", "S0", "Memory", f"Obsidian · {s.vault_dir.name}", st("vault" in at)),
            card("gate", "gate · risk tiers", "S0", "Guardian", "act.py", st(acting),
                 "tiering the agents' calls" if acting else ""),
            card("replycheck", "reply check", "S0", "Guardian", "meeting.py · code", st(live["meeting"]),
                 "exact times, the right name, nothing private" if live["meeting"] else ""),
            card("planner", "day planner", "S0", "Planner", "OR-Tools CP-SAT", st(self.planning > 0),
                 "placing tasks around meetings" if self.planning else ""),
            card("herald", "herald · routing", "S0", "Herald", "rules · quiet hours", "idle",
                 f"{open_cards} open card{'s' if open_cards != 1 else ''}" if open_cards else ""),
            card("diplomat", "diplomat · minimizer", "S0", "Diplomat", "diplomat.py · code", st(live["diplomat"]),
                 "only times leave, never the calendar" if live["diplomat"] else ""),
            card("memgate", "memory gate", "S1", "Librarian", s1, st("gate" in at, ok1),
                 "is this worth remembering?" if "gate" in at else ""),
            card("judge", "relevance", "S1", "Researcher", s1, st(self.asking > 0, ok1),
                 "dropping what is surely irrelevant" if self.asking else ""),
            card("support", "support check", "S1", "Guardian", s1, st(self.asking > 0, ok1),
                 "does the answer follow from what it cites?" if self.asking else ""),
            card("memcheck", "memory checks", "S1", "Memory", s1, st(False, ok1)),
            card("todo", "to-do filter", "S1", "Planner", s1, st(self.planning > 0, ok1),
                 "is this a real to-do?" if self.planning else ""),
            card("ask", "ask pipeline", "S2", "Researcher", s2, st(self.asking > 0, ok2),
                 "answering a question" if self.asking else ""),
            card("research", "research agent", "S2", "Researcher", f"{s2} · over MCP", st(False, ok2)),
            card("workbench", "operator agent", "S2", "Operator", s2,
                 st(live["act"], ok2 and self.workbench, any(r.pending and r.kind == "act" for r in runs)),
                 "" if self.workbench else "no sandbox (data/raw/workbench)",
                 pending=sum(1 for r in runs if r.pending is not None and r.kind == "act")),
            card("meeting", "meeting writer", "S2", "Operator", s2,
                 st(live["meeting"], ok2 and self.workbench, any(r.pending and r.kind == "meeting" for r in runs)),
                 "drafting a reply" if live["meeting"] else "",
                 pending=sum(1 for r in runs if r.pending is not None and r.kind == "meeting")),
            card("intent", "intent check", "S2", "Guardian", s2, st(acting, ok2),
                 "does this call do what was asked?" if acting else ""),
            card("builder", "memory builder", "S2", "Librarian", s2, st("extracted" in at, ok2),
                 "extracting beliefs" if "extracted" in at else ""),
            card("second", "second opinion", "S2", None, s2, st(False, ok2)),
            card("owner", "you · this page", "H", "Guardian", "127.0.0.1", "waiting" if waiting else "idle",
                 pending=waiting),
            card("watch", f"watch {watch_name}" if devices else "watch", "H", "Herald",
                 "not paired" if not devices else "listener off" if not self.lan else
                 "not seen yet" if seen is None else f"seen {_ago(now - seen)} ago",
                 "idle" if devices and self.lan and seen and now - seen < 90 else "offline", device=True,
                 last_seen=seen),
        ]
        with connect(s.database_url) as conn:
            for a in out:
                pred = AGENT_ROWS.get(a["id"])
                a.update({"p50": None, "p95": None, "today": None, "last": None})
                if a["id"] == "parser":
                    a["today"] = conn.execute("SELECT count(*) AS n FROM items WHERE ingested_at >= "
                                              "date_trunc('day', now())").fetchone()["n"]
                if pred is None:
                    continue
                r = conn.execute(
                    f"SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50, percentile_cont(0.95) "
                    f"WITHIN GROUP (ORDER BY latency_ms) AS p95 FROM (SELECT latency_ms FROM judgements WHERE {pred} "
                    f"ORDER BY id DESC LIMIT 200) t", {"mem": MEMORY_QUESTIONS}).fetchone()
                a["p50"] = round(r["p50"]) if r["p50"] is not None else None
                a["p95"] = round(r["p95"]) if r["p95"] is not None else None
                a["today"] = conn.execute(f"SELECT count(*) AS n FROM judgements WHERE ({pred}) AND created_at >= "
                                          f"date_trunc('day', now())", {"mem": MEMORY_QUESTIONS}).fetchone()["n"]
                last = conn.execute(f"SELECT question, value, created_at FROM judgements WHERE {pred} ORDER BY id DESC "
                                    f"LIMIT 1", {"mem": MEMORY_QUESTIONS}).fetchone()
                if last:
                    a["last"] = {"question": last["question"], "value": last["value"],
                                 "at": last["created_at"].isoformat(timespec="seconds")}
        return out

    def agent(self, agent_id: str) -> dict:
        """One agent: its row from agents(), its last 20 decisions and the latencies of its last 60."""
        a = next((x for x in self.agents() if x["id"] == agent_id), None)
        if a is None:
            raise KeyError(agent_id)
        pred = AGENT_ROWS.get(agent_id)
        if pred is None:
            return {**a, "decisions": [], "latencies": []}
        with connect(self.settings.database_url) as conn:
            rows = conn.execute(f"SELECT id, question, subject, tier, model, value, probs, settled, latency_ms, "
                                f"created_at FROM judgements WHERE {pred} ORDER BY id DESC LIMIT 60",
                                {"mem": MEMORY_QUESTIONS}).fetchall()
        return {**a, "latencies": [round(r["latency_ms"]) for r in reversed(rows)], "decisions": [
            {"id": r["id"], "question": r["question"], "subject": r["subject"], "tier": r["tier"], "value": r["value"],
             "p": round(r["probs"].get(r["value"], 0.0), 3) if r["value"] else 0.0, "settled": r["settled"],
             "latency_ms": round(r["latency_ms"]), "at": r["created_at"].isoformat(timespec="seconds")}
            for r in rows[:20]]}

    def schema(self) -> dict:
        """Tables and views of this brain (information_schema), with row counts (exact under 200k rows, else the
        planner's estimate), columns, and foreign keys (a view links to the tables it reads)."""
        with connect(self.settings.database_url) as conn:
            rels = conn.execute(
                "SELECT t.table_name AS name, t.table_type AS type, c.reltuples::bigint AS est FROM "
                "information_schema.tables t LEFT JOIN pg_class c ON c.relname = t.table_name AND c.relnamespace = "
                "'public'::regnamespace WHERE t.table_schema = 'public' ORDER BY 1").fetchall()
            mats = conn.execute("SELECT matviewname AS name FROM pg_matviews WHERE schemaname = 'public'").fetchall()
            cols: dict[str, list] = {}
            for r in conn.execute("SELECT table_name, column_name, CASE WHEN data_type = 'USER-DEFINED' THEN udt_name "
                                  "ELSE data_type END AS type FROM information_schema.columns WHERE table_schema = "
                                  "'public' ORDER BY table_name, ordinal_position"):
                cols.setdefault(r["table_name"], []).append([r["column_name"], r["type"]])
            fks = [[r["src"], r["dst"], r["col"]] for r in conn.execute(
                "SELECT c.conrelid::regclass::text AS src, c.confrelid::regclass::text AS dst, a.attname AS col "
                "FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1] "
                "WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace ORDER BY 1, 2")]
            fks += [[r["view_name"], r["table_name"], ""] for r in conn.execute(
                "SELECT DISTINCT view_name, table_name FROM information_schema.view_table_usage WHERE view_schema = "
                "'public' AND table_schema = 'public' AND view_name <> table_name")]
            tables = []
            for r in [*rels, *({"name": m["name"], "type": "MATERIALIZED VIEW", "est": None} for m in mats)]:
                kind = {"BASE TABLE": "table", "VIEW": "view"}.get(r["type"], "matview")
                rows = None
                if kind == "table":
                    rows = r["est"] if r["est"] is not None and r["est"] >= 200_000 else conn.execute(
                        pgsql.SQL("SELECT count(*) AS n FROM {}").format(pgsql.Identifier(r["name"]))).fetchone()["n"]
                big = kind == "table" and r["est"] is not None and r["est"] >= 200_000
                tables.append({"name": r["name"], "kind": kind, "rows": rows, "estimate": big,
                               "columns": cols.get(r["name"], [])})
        return {"tables": tables, "fks": fks}

    def table(self, name: str) -> dict:
        """A sample of one table's rows, read through the read-only role."""
        known = {t["name"]: t for t in self.schema()["tables"]}
        if name not in known:
            raise KeyError(name)
        reader = make_conninfo(self.settings.database_url, user="engram_reader", password="engram_reader")
        with connect(reader) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '3s'")
            cur = conn.execute(pgsql.SQL("SELECT * FROM {} LIMIT 12").format(pgsql.Identifier(name)))
            columns = [d.name for d in cur.description or []]
            rows = [[_short(r[c]) for c in columns] for r in cur.fetchall()]
            conn.rollback()
        return {**known[name], "sample": {"columns": columns, "rows": rows}}

    def timeline(self, q: dict[str, str]) -> dict:
        """Beliefs with both their times, current and superseded: valid (in the world) and recorded (in the brain)."""
        with connect(self.settings.database_url) as conn:
            rows = conn.execute(
                "SELECT id, kind, actor, other, statement, lower(valid) AS vs, upper(valid) AS ve, lower(recorded) AS "
                "rs, upper(recorded) AS re, supersedes, confidence, item_id, quote, author, status FROM beliefs "
                "WHERE (%(kind)s::text IS NULL OR kind = %(kind)s) AND (%(p)s::text IS NULL OR actor ILIKE %(p)s OR "
                "other ILIKE %(p)s) ORDER BY id DESC LIMIT 400",
                {"kind": q.get("kind") or None, "p": f"%{q['person']}%" if q.get("person") else None}).fetchall()
            people = [r["who"] for r in conn.execute(
                "SELECT who FROM (SELECT actor AS who FROM current_beliefs UNION ALL SELECT other FROM "
                "current_beliefs) t WHERE who <> '' GROUP BY who ORDER BY count(*) DESC LIMIT 8")]
        iso = lambda d: d.isoformat(timespec="seconds") if d else None       # noqa: E731
        return {"people": people, "beliefs": [
            {"id": r["id"], "kind": r["kind"], "actor": r["actor"], "other": r["other"], "statement": r["statement"],
             "valid": [iso(r["vs"]), iso(r["ve"])], "recorded": [iso(r["rs"]), iso(r["re"])],
             "supersedes": r["supersedes"], "confidence": r["confidence"], "item_id": r["item_id"], "quote": r["quote"],
             "status": r["status"], "tier": "H" if r["author"] == "owner" else "S2"} for r in rows]}

    def belief(self, belief_id: int) -> dict | None:
        """One belief with its provenance: the item it came from, the verbatim quote, and the gate's judgement."""
        with connect(self.settings.database_url) as conn:
            b = conn.execute("SELECT b.*, lower(b.valid) AS vs, lower(b.recorded) AS rs, upper(b.recorded) AS re, "
                             "i.subject, i.from_addr, i.sent_at FROM beliefs b JOIN items i ON i.id = b.item_id WHERE "
                             "b.id = %s", (belief_id,)).fetchone()
            if b is None:
                return None
            gate = conn.execute("SELECT tier, model, value, probs, created_at FROM judgements WHERE subject = %s AND "
                                "question = ANY(%s) ORDER BY id DESC LIMIT 3",
                                (f"item:{b['item_id']}", MEMORY_QUESTIONS)).fetchall()
        return {"id": b["id"], "kind": b["kind"], "statement": b["statement"], "actor": b["actor"], "other": b["other"],
                "quote": b["quote"], "confidence": b["confidence"], "status": b["status"], "trust": b.get("trust"),
                "tier": "H" if b["author"] == "owner" else "S2", "current": b["re"] is None,
                "valid_from": _date(b["vs"]), "recorded": _date(b["rs"]), "due_at": _date(b["due_at"]),
                "item": {"id": b["item_id"], "subject": b["subject"], "from": b["from_addr"],
                         "date": _date(b["sent_at"])},
                "gate": [{"tier": g["tier"], "model": g["model"], "value": g["value"],
                          "p": round(g["probs"].get("yes", 0.0), 3)} for g in gate]}

    def find(self, q: dict[str, str]) -> dict:
        """The command palette's search: items by subject or sender, beliefs by statement, people by name."""
        text = q.get("q", "").strip()
        if len(text) < 2:
            return {"items": [], "beliefs": [], "people": []}
        like = "%" + text.replace("%", "").replace("_", "\\_") + "%"
        with connect(self.settings.database_url) as conn:
            items = conn.execute("SELECT id, subject, from_addr, sent_at FROM items WHERE subject ILIKE %s OR "
                                 "from_addr ILIKE %s ORDER BY sent_at DESC NULLS LAST LIMIT 6", (like, like)).fetchall()
            beliefs = conn.execute("SELECT id, kind, statement FROM current_beliefs WHERE statement ILIKE %s ORDER BY "
                                   "id DESC LIMIT 6", (like,)).fetchall()
            people = conn.execute("SELECT id, name, n_items FROM people WHERE name ILIKE %s OR %s ILIKE ANY(aliases) "
                                  "ORDER BY n_items DESC LIMIT 6", (like, text.lower())).fetchall()
        return {"items": [{**i, "sent_at": _date(i["sent_at"])} for i in items], "beliefs": beliefs, "people": people}

    def adds_list(self) -> list[dict]:
        return [{"id": rid, "title": r.title, "status": r.status, "item": r.item, "stages": len(r.stages)}
                for rid, r in list(self.adds.items())[-20:]][::-1]

    # ------------------------------------------------------------------------------------------------ adding

    def add(self, body: dict) -> dict:
        run_id, run = uuid.uuid4().hex[:8], AddRun(body.get("title") or "Note")
        self.adds[run_id] = run
        self.worker.submit(self._add, run, body)
        return {"id": run_id}

    def _add(self, run: AddRun, body: dict) -> None:
        from time import perf_counter

        from .memory import REMEMBER, build, bulk, reading_text
        from .sources.enron import Message
        from .store import ingest_messages
        from .vault import sync

        s = self.settings

        def stage(name: str, t0: float, detail: str) -> None:
            run.stages.append({"stage": name, "ms": round((perf_counter() - t0) * 1000), "detail": detail})

        try:
            text = body["text"].strip()
            sent = _day(body.get("date")) or datetime.now()
            sender = (body.get("from") or "owner").strip().lower()
            msg = Message(f"upload/{uuid.uuid4().hex}", "upload", sent, sender, (), (), run.title, text)
            with connect(s.database_url) as conn:
                t = perf_counter()
                ingest_messages(conn, [msg], {"owner"}, "upload", "note")
                conn.commit()
                run.item = conn.execute("SELECT item_id FROM item_refs WHERE ref = %s",
                                        (msg.ref,)).fetchone()["item_id"]
                n = conn.execute("SELECT count(*) AS n FROM chunks WHERE item_id = %s", (run.item,)).fetchone()["n"]
                stage("stored", t, f"item {run.item}: split, {n} chunk(s), keyword postings")
                t = perf_counter()
                index.embed_pending(conn, self.embed, model=s.embed_model)
                stage("embedded", t, f"{n} vector(s) with {s.embed_model}")
                row = conn.execute("SELECT id, kind, sent_at, from_addr, to_addrs, subject, body, quoted FROM items "
                                   "WHERE id = %s", (run.item,)).fetchone()
                t = perf_counter()
                owner_says = body.get("remember") is True        # "remember …" on the watch: the owner decided
                if bulk(row) and not owner_says:
                    stage("gate", t, "S0: bulk or machine mail, nothing to remember")
                else:
                    if owner_says:
                        stage("gate", t, "you said remember: no judge needed (a human label for the judge)")
                    else:
                        a = self.judge().answer("S1", self.judge().s1, REMEMBER, reading_text(row),
                                                f"item:{run.item}")
                        p = a.probs.get("yes", 0.0) if a.logprobs else 1.0
                        stage("gate", t, f"S1 ({a.model}): P(worth remembering) = {p:.2f}")
                    t = perf_counter()
                    stats = build(conn, self.judge(), self.llm, s.s2_model, s.owner, s.owner_timezone,
                                  ids=[run.item], owner_says=[run.item] if owner_says else ())
                    stage("extracted", t, f"S2 ({s.s2_model}): {stats.beliefs} belief(s)" if stats.passed
                          else "below the gate's threshold: not extracted")
                    run.beliefs = [dict(b) for b in conn.execute(
                        "SELECT id, kind, statement, actor, other FROM current_beliefs WHERE item_id = %s",
                        (run.item,))]
                t = perf_counter()
                sync(conn, s.vault_dir)
                stage("vault", t, f"Obsidian vault updated ({s.vault_dir.name})")
            run.status = "done"
            self.sweep()                                # a new arrival or a note due soon reaches the watch now
        except Exception as e:
            run.status, run.error = "error", f"{type(e).__name__}: {e}"

    def add_state(self, run_id: str) -> dict:
        r = self.adds[run_id]
        return {"title": r.title, "status": r.status, "stages": r.stages, "item": r.item, "beliefs": r.beliefs,
                "error": r.error, "graph": self.item_node(r.item) if r.item and r.status == "done" else None}

    # ------------------------------------------------------------------------------------------------ acting

    def act(self, body: dict) -> dict:
        if not self.workbench:
            raise LookupError("no WorkBench sandbox (clone it into data/raw/workbench)")
        run_id, run = uuid.uuid4().hex[:8], AgentRun(body["request"])
        self.runs[run_id] = run
        domains = tuple(body["domains"]) if body.get("domains") else None
        threading.Thread(target=self._act, args=(run, run_id, domains, int(body.get("autonomy", 1))),
                         daemon=True).start()
        return {"id": run_id}

    def _approver(self, run: AgentRun, run_id: str, card: dict | None = None):
        """The owner as the gate's approver: the action waits (on the page and the watch) until decided, times out
        as a no, and the decision goes into the ledger. `card` adds what the owner sees beyond the preview (the
        judge never reads it)."""
        def approve(request: str, tool: Tool, args: dict, verdict: Verdict | None) -> bool:
            t0, preview = time.monotonic(), describe(tool, args)
            with self.changes:
                run.decided.clear()
                run.pending = {"tool": tool.name, "effect": tool.effect, "preview": preview,
                               "judge": _verdict(verdict)} | ({"card": card} if card else {})
                run.status = "waiting"
                self._changed()
            run.decided.wait(APPROVAL_WAIT)
            with self.changes:          # the timeout and a late decide() settle under one lock: exactly one wins
                if not run.decided.is_set():
                    run.approved, run.channel = False, "timeout"
                    run.decided.set()
                run.pending, run.status = None, "running"
                self._changed()
            self._record(run_id, preview, run.approved, run.channel, (time.monotonic() - t0) * 1000)
            return run.approved
        return approve

    def _act(self, run: AgentRun, run_id: str, domains: tuple[str, ...] | None, autonomy: int) -> None:
        approve = self._approver(run, run_id)
        s = self.settings
        try:                            # each run is a fresh sandbox: WorkBench keeps its state per thread
            with Judge(s.database_url, None, OllamaScorer(s.ollama_url, s.s2_model)) as judge:
                r = agent.run(self.llm, s.s2_model, wb.SYSTEM, run.request, wb.tools(domains),
                              Gate(judge, approve, autonomy), f"act:{run_id}", on_step=lambda st:
                              run.steps.append(_step(st)))
            run.answer = r.answer if r.answer is not None else "(stopped at the turn limit)"
            run.status = "done"
        except Exception as e:          # shown in the page; the gate itself fails closed
            run.answer, run.status = f"{type(e).__name__}: {e}", "error"

    # ----------------------------------------------------------------------- Diplomat: agree a time with a peer

    def diplomat(self, body: dict) -> dict:
        """Agree a meeting time with another company's secretary (a peer in data/diplomat/peers.json). Every
        message out, and the booking, waits for the owner on the page or the watch."""
        from . import diplomat as dp

        if not self.workbench:
            raise LookupError("no WorkBench sandbox (clone it into data/raw/workbench)")
        known = dp.peers(self.settings.diplomat_peers)
        name = str(body.get("peer", ""))
        if name not in known:
            raise LookupError(f"unknown secretary {name!r}; known: {', '.join(known) or 'none'}")
        topic, minutes = str(body.get("topic", "")).strip(), int(body.get("minutes", 30))
        dp.minimize("propose", "check", topic or "meeting", minutes, [])          # refuse a leaky topic up front
        run_id = uuid.uuid4().hex[:8]
        run = AgentRun(f"Agree a time with {name} about '{topic or 'meeting'}'", kind="diplomat")
        self.runs[run_id] = run
        threading.Thread(target=self._diplomat, args=(run, run_id, name, known[name], topic or "meeting", minutes),
                         daemon=True).start()
        return {"id": run_id}

    def _diplomat(self, run: AgentRun, run_id: str, name: str, peer: dict, topic: str, minutes: int) -> None:
        from . import diplomat as dp
        from . import meeting as mt

        s = self.settings
        try:                            # the owner's calendar: this run's fresh sandbox plus what was booked here
            with Judge(s.database_url, None, OllamaScorer(s.ollama_url, s.s2_model)) as judge:
                me = dp.Side("me", mt.wb_calendar() + list(self.booked), Gate(judge, self._approver(run, run_id)),
                             mt.WB_NOW)
                create = {t.name: t for t in wb.tools(("calendar",))}["calendar.create_event"].run
                got = dp.negotiate(me, name, dp.poster(peer["url"], peer["token"], s.owner), topic, minutes, create)
            run.steps += [{"tool": "Diplomat", "args": {}, "ran": True, "observation": line, "gate": None}
                          for line in me.log]
            if got is not None:
                self.booked.append(mt.Event(got, minutes, topic))
            run.answer = f"Agreed with {name}: {mt.when(got)}" if got else f"No time agreed with {name}"
            run.status = "done"
        except Exception as e:          # shown in the page; nothing leaves without its gate check
            run.answer, run.status = f"{type(e).__name__}: {e}", "error"

    # ------------------------------------------------------------------------------ Feature 2: meeting reply

    def meeting(self, body: dict) -> dict:
        """Answer a meeting request in the WorkBench sandbox: an inbox email by `email_id`, or a new one (`sender`,
        `subject`, `body`) put in the inbox first. Its steps and the owner's approvals show like an agent run."""
        if not self.workbench:
            raise LookupError("no WorkBench sandbox (clone it into data/raw/workbench)")
        if not body.get("email_id") and not (body.get("sender") and str(body.get("body", "")).strip()):
            raise ValueError("give email_id, or sender and body")
        title = body.get("email_id") or f"{body['sender']}: {body.get('subject') or 'meeting'}"
        run_id, run = uuid.uuid4().hex[:8], AgentRun(f"Answer the meeting request {title}", kind="meeting")
        self.runs[run_id] = run
        threading.Thread(target=self._meeting, args=(run, run_id, body), daemon=True).start()
        return {"id": run_id}

    def _meeting(self, run: AgentRun, run_id: str, body: dict) -> None:
        from . import meeting as mt

        s = self.settings
        try:                            # a fresh sandbox per thread: WorkBench keeps its state per thread
            email = mt.wb_email(body["email_id"]) if body.get("email_id") else mt.wb_add_email(
                body["sender"], body.get("subject") or "Meeting", body["body"], mt.WB_NOW)
            events, contacts = mt.wb_calendar() + list(self.booked), mt.wb_contacts(email.sender)
            pr = self.worker.submit(mt.propose, email, self.judge(), self.llm, s.s2_model, events, mt.WB_NOW,
                                    contacts).result()               # the in-process judge runs on its thread
            run.steps += [_role_step(x) for x in pr.steps]
            card = {"headline": pr.headline, "reply": pr.reply, "slots": [mt.when(t) for t in pr.slots]}
            with Judge(s.database_url, None, OllamaScorer(s.ollama_url, s.s2_model)) as judge:
                tools = {t.name: t for t in wb.tools(("email", "calendar"))}
                done = mt.carry_out(pr, tools, Gate(judge, self._approver(run, run_id, card)), f"meeting:{run_id}",
                                    on_step=lambda x: run.steps.append(_role_step(x)))
            sent = [n for n, c, _ in done if c.allowed]
            if "calendar.create_event" in sent:
                self.booked.append(mt.Event(pr.slots[0], pr.minutes, pr.topic))
            run.answer = (f"{pr.headline}. " + ("Done: " + ", ".join(sent) if sent else
                                                 "Nothing sent." if done else "Nothing to do."))
            run.status = "done"
        except Exception as e:          # shown in the page; nothing runs without its gate check
            run.answer, run.status = f"{type(e).__name__}: {e}", "error"

    def decide(self, run_id: str, approve: bool, channel: str = "page") -> dict:
        run = self.runs[run_id]
        with self.changes:                  # one decision per pending action, whichever device is first
            if run.pending is None or run.decided.is_set():
                raise LookupError("nothing is waiting for a decision")
            if channel.startswith("watch") and run.pending["effect"] == "destructive":
                raise PermissionError("destructive actions are decided on the laptop, not the watch")
            run.approved, run.channel = bool(approve), channel
            run.decided.set()
        return {"ok": True}

    def pending(self, since: int | None = None, wait: float = 0.0) -> dict:
        """Actions waiting for the owner. Given the `version` a caller last saw, wait up to `wait` seconds for a
        change first (a long-poll: the watch hears of a new approval within a second, without a cloud push)."""
        with self.changes:
            if since is not None:
                self.changes.wait_for(lambda: self.version != since, timeout=min(wait, LONG_POLL))
            version = self.version
        waiting = [(rid, r.request, r.pending) for rid, r in list(self.runs.items())]
        return {"version": version, "pending": [{"run": rid, "request": request, **p,
                                                 "on_watch": p["effect"] != "destructive"}
                                                for rid, request, p in waiting if p is not None]}

    # ------------------------------------------------------------------------------------------------ Herald

    def start_herald(self) -> None:
        """Herald's two background threads: every minute, the roles' sweep (a snoozed card coming back also wakes
        the watch); and a LISTEN on the cards table, so a card any process posts reaches the watch at once."""
        threading.Thread(target=self._sweeping, daemon=True, name="herald-sweep").start()
        threading.Thread(target=self._listening, daemon=True, name="herald-listen").start()

    def sweep(self) -> list[dict]:
        from .planner import owner_names

        s = self.settings
        with connect(s.database_url) as conn:
            return herald.sweep(conn, datetime.now(UTC), s.herald_timezone or herald.local_timezone(),
                                owner_names(conn, s.owner))

    def cards(self, deliver: bool = False) -> list[dict]:
        with connect(self.settings.database_url) as conn:
            return herald.cards(conn, datetime.now(UTC), deliver)

    def card(self, card_id: int, action: str, by: str) -> dict:
        with connect(self.settings.database_url) as conn:
            return herald.decide(conn, card_id, action, by, datetime.now(UTC))

    def tap(self, card_id: int, action: str) -> dict:
        """The owner answers a Herald card on the page: the same answer as a watch tap, and the watch hears of it."""
        r = self.card(card_id, action, "page")
        self._changed()
        return r

    # ----------------------------------------------------------------------------------- Planner: the day plan

    def plan(self, q: dict[str, str]) -> dict:
        """The latest plan for `day` (default: the most recently planned day), as stored; nothing is solved."""
        with connect(self.settings.database_url) as conn:
            days = [r["day"].isoformat() for r in conn.execute(
                "SELECT day FROM plan_entries GROUP BY day ORDER BY max(created_at) DESC LIMIT 12").fetchall()]
            day = _day(q.get("day") or (days[0] if days else None))
            if day is None:
                return {"day": None, "version": 0, "entries": [], "planned_days": [],
                        "timezone": self.settings.owner_timezone}
            rows = conn.execute(
                "SELECT belief_id, title, starts, ends, kind, status, why FROM plan_entries WHERE day = %s AND "
                "version = (SELECT max(version) FROM plan_entries WHERE day = %s) ORDER BY starts NULLS LAST, id",
                (day.date(), day.date())).fetchall()
            version = conn.execute("SELECT coalesce(max(version), 0) AS v FROM plan_entries WHERE day = %s",
                                   (day.date(),)).fetchone()["v"]
        return {"day": day.date().isoformat(), "version": version, "planned_days": days,
                "timezone": self.settings.owner_timezone, "entries": [self._entry(r) for r in rows]}

    def _entry(self, r: dict) -> dict:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(self.settings.owner_timezone)
        hm = lambda t: t.astimezone(tz).strftime("%H:%M") if t else None      # noqa: E731
        return {"belief": r["belief_id"], "title": r["title"], "starts": hm(r["starts"]), "ends": hm(r["ends"]),
                "kind": r["kind"], "status": r["status"], "why": r["why"]}

    def replan(self, body: dict) -> dict:
        """Plan `day` again (a new version): at `now` (HH:MM, the owner's zone) what was missed is marked and placed
        again. The to-do filter is the in-process judge, so the whole solve runs on its thread."""
        from datetime import time as dtime
        from zoneinfo import ZoneInfo

        from .planner import owner_names, plan_day

        s = self.settings
        day = _day(str(body.get("day", "")))
        if day is None:
            raise ValueError("give day as YYYY-MM-DD")
        at = datetime.combine(day.date(), dtime.fromisoformat(body["now"]), ZoneInfo(s.owner_timezone)) \
            if body.get("now") else None

        def solve() -> int:
            with connect(s.database_url) as conn:
                return plan_day(conn, day.date(), s.owner_timezone, owner_names(conn, s.owner), at, self.judge())[0]

        self.planning += 1
        t0 = time.monotonic()
        try:
            self.worker.submit(solve).result()
        finally:
            self.planning -= 1
        return {**self.plan({"day": day.date().isoformat()}), "seconds": round(time.monotonic() - t0, 1)}

    # ------------------------------------------------------------------------ Operator: meeting requests to answer

    def meeting_inbox(self) -> list[dict]:
        """WorkBench inbox emails that ask for a meeting and had arrived by WorkBench's clock (its "now"): the
        requests the meeting reply can answer."""
        import csv

        from .meeting import WB_NOW

        path = self.settings.workbench_dir / "data" / "processed" / "emails.csv"
        if not self.workbench or not path.exists():
            return []
        asks = ("schedule a meeting", "when are you free", "set up a meeting", "find a time", "can we meet")
        with path.open(newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["inbox/outbox"] == "inbox" and r["sent_datetime"] <= f"{WB_NOW}"
                    and any(w in r["body"].lower() for w in asks)]
        rows.sort(key=lambda r: r["sent_datetime"], reverse=True)
        return [{"email_id": r["email_id"], "sender": r["sender/recipient"], "subject": r["subject"],
                 "sent": r["sent_datetime"], "body": r["body"].replace("\\n", "\n")[:600]} for r in rows[:15]]

    def _sweeping(self) -> None:
        visible: list[int] = []
        while True:
            try:
                self.sweep()
                now_visible = [c["id"] for c in self.cards()]
                if now_visible != visible:
                    visible = now_visible
                    self._changed()
            except Exception as e:                  # the database may be restarting: try again next minute
                print(f"herald sweep: {type(e).__name__}: {e}")
            time.sleep(60)

    def _listening(self) -> None:
        while True:
            try:
                with psycopg.connect(self.settings.database_url, autocommit=True) as conn:
                    conn.execute("LISTEN herald")
                    for _ in conn.notifies():
                        self._changed()
            except Exception:
                time.sleep(5)

    def _changed(self) -> None:
        with self.changes:
            self.version += 1
            self.changes.notify_all()

    def _record(self, run_id: str, preview: str, approved: bool, channel: str, ms: float) -> None:
        """The owner's decision goes into the hash-chained ledger next to the judge's (tier H). If the write fails,
        the run fails and the action does not run."""
        value = "yes" if approved else "no"
        with connect(self.settings.database_url) as conn:
            append(conn, "approve", f"act:{run_id}", hashlib.sha256(preview.encode()).hexdigest(),
                   Answer("H", f"owner:{channel}", {}, {"yes": float(approved), "no": float(not approved)}, value,
                          True, ms))

    # ------------------------------------------------------------------------------------------------- voice

    def voice(self, wav: bytes) -> dict:
        """A spoken clip: transcribed here, then a note to remember ("remember …") or a question for the brain."""
        audio = samples(wav)
        if len(audio) < 0.3 * 16_000:
            raise ValueError("too short to hear anything")
        t0 = time.monotonic()
        heard = self.worker.submit(self.transcribe, audio).result()       # MLX: on the model thread
        heard_ms = round((time.monotonic() - t0) * 1000)
        if not heard:
            raise ValueError("didn't catch that")
        kind, text = route(heard)
        if kind == "add":
            return {"heard": heard, "kind": "add", "heard_ms": heard_ms,
                    **self.add({"text": text, "title": "Voice note", "remember": True})}
        return {"heard": heard, "kind": "ask", "heard_ms": heard_ms, **self.ask({"question": text})}

    def run_state(self, run_id: str) -> dict:
        r = self.runs[run_id]
        return {"request": r.request, "status": r.status, "steps": r.steps, "pending": r.pending,
                "answer": r.answer}


# Which ledger rows are each agent's decisions (SQL over judgements; the question sets below). Code-only agents
# (parser, vault, gate, reply check, planner, herald, diplomat) make no judgements, so they have none. S1 rows go
# to the role that asked; an S2 row is either an S2 agent's own (intent, extraction gates, ask, research) or the
# 14B's second opinion on something S1 was unsure of.
GATES = ("remember", "meeting_request")                                  # the Librarian's: keep it? a meeting?
CHECKS = ("fulfilled", "contradicts", "same_belief")                     # Memory's
EXTRACT = (*GATES, "has_commitment", "has_decision", "has_meeting")      # the memory builder's on S2
OWN_S2 = (*EXTRACT, "intent")                                             # S2 decisions that are no second opinion
S1_OWNED = (*GATES, *CHECKS, "todo", "supported")                        # S1 questions with a role card of their own


def _in(names: tuple[str, ...]) -> str:
    """`question IN (...)` over the constant names above (never user input)."""
    return "question IN (" + ", ".join(f"'{n}'" for n in names) + ")"


AGENT_ROWS = {
    "memgate": f"tier = 'S1' AND {_in(GATES)}",
    "memcheck": f"tier = 'S1' AND {_in(CHECKS)}",
    "todo": "tier = 'S1' AND question = 'todo'",
    "support": "tier = 'S1' AND question = 'supported'",
    "judge": f"tier = 'S1' AND NOT {_in(S1_OWNED)}",
    "intent": "tier = 'S2' AND question = 'intent'",
    "builder": f"tier = 'S2' AND {_in(EXTRACT)}",
    "ask": f"tier = 'S2' AND subject LIKE '%%|ask:%%' AND NOT {_in(OWN_S2)}",
    "research": f"tier = 'S2' AND (subject LIKE '%%|scan' OR subject LIKE '%%|check') AND NOT {_in(OWN_S2)}",
    "second": f"tier = 'S2' AND NOT {_in(OWN_S2)} AND subject NOT LIKE '%%|ask:%%' AND subject NOT LIKE '%%|scan' "
              "AND subject NOT LIKE '%%|check'",
    "owner": "tier = 'H' AND model NOT LIKE 'owner:watch%%'",
    "watch": "tier = 'H' AND model LIKE 'owner:watch%%'",
}


def agent_for(row: dict) -> str:
    """The agent a ledger row belongs to (the same split as AGENT_ROWS)."""
    tier, question, subject = row["tier"], row["question"], row["subject"]
    if tier == "H":
        return "watch" if row["model"].startswith("owner:watch") else "owner"
    if tier == "S1":
        return ("memgate" if question in GATES else "memcheck" if question in CHECKS else "todo" if question == "todo"
                else "support" if question == "supported" else "judge")
    if question == "intent":
        return "intent"
    if question in EXTRACT:
        return "builder"
    if "|ask:" in subject:
        return "ask"
    if subject.endswith(("|scan", "|check")):
        return "research"
    return "second"


def entry_for(row: dict) -> str:
    """The code (S0) a decision's material came through before any model saw it."""
    subject, question = row["subject"], row["question"]
    if subject.startswith("diplomat:"):
        return "diplomat"
    if subject.startswith(("act:", "wb:", "meeting:")):
        return "gate"
    if question.startswith("herald:"):
        return "herald"
    if question == "todo":
        return "planner"
    return "parser"


class Brains:
    """One Brain per database, made on first use and kept: a profile's requests always reach its own."""

    def __init__(self, settings: Settings, workbench: bool):
        self.settings, self.workbench = settings, workbench
        self.lock = threading.Lock()
        self.cache: dict[str, Brain] = {}

    def url(self, database: str) -> str:
        """The server's URL with another database: still a URL, so everything that reads the name keeps working."""
        base, _, query = self.settings.database_url.partition("?")
        if "://" not in base:
            return make_conninfo(self.settings.database_url, dbname=database)
        return f"{base.rsplit('/', 1)[0]}/{database}" + (f"?{query}" if query else "")

    def get(self, database: str) -> Brain:
        with self.lock:
            if database not in self.cache:
                self.cache[database] = Brain(self.settings.model_copy(update={"database_url": self.url(database)}),
                                             self.workbench)
            return self.cache[database]

    def exists(self, database: str) -> bool:
        with psycopg.connect(make_conninfo(self.settings.database_url, dbname="postgres"), connect_timeout=3) as c:
            return c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone() is not None

    def close(self) -> None:
        for b in self.cache.values():
            b.llm.close()


# ---------------------------------------------------------------------------------------------------- HTTP

def make_handler(brains: Brains, hosts: set[str], profiles: Profiles) -> type[BaseHTTPRequestHandler]:
    origins = {f"http://{h}" for h in hosts}
    tiles: dict[str, tuple[float, dict]] = {}          # the login tiles' counts and graph shapes, cached for 15 s

    def tile(p: dict) -> dict:
        at, t = tiles.get(p["name"], (0.0, None))
        if t is None or time.monotonic() - at > 15:
            try:
                b = brains.get(p["database"])
                t = {"counts": b.counts(), "graph": b.sample()}
            except psycopg.Error:
                t = {"counts": None, "graph": {"nodes": [], "links": []}, "error": "database not reachable"}
            tiles[p["name"]] = (time.monotonic(), t)
        return {"name": p["name"], "color": p["color"], **t}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:     # quiet: the page shows what happens
            pass

        def _refuse_foreign(self) -> bool:
            origin = self.headers.get("Origin")
            if self.headers.get("Host") not in hosts or (origin is not None and origin not in origins):
                self._send(HTTPStatus.FORBIDDEN, {"error": "local page only"})
                return True
            return False

        def _send(self, status: HTTPStatus, payload: Any, content_type: str = "application/json",
                  cookie: str | None = None) -> None:
            body = payload if isinstance(payload, bytes) else json.dumps(payload, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if content_type.startswith("text/html"):
                self.send_header("Content-Security-Policy", CSP)
                self.send_header("X-Frame-Options", "DENY")
            if cookie is not None:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(body)

        def _token(self) -> str | None:
            jar = SimpleCookie()
            try:
                jar.load(self.headers.get("Cookie", ""))
            except Exception:
                return None
            return jar[COOKIE].value if COOKIE in jar else None

        def _profile(self) -> dict | None:
            return profiles.session(self._token())

        def _brain(self) -> Brain | None:
            """The signed-in profile's brain, or None after answering 401."""
            p = self._profile()
            if p is None:
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "sign in to a brain first"})
                return None
            return brains.get(p["database"])

        def do_GET(self) -> None:
            if self._refuse_foreign():
                return
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            parts = url.path.strip("/").split("/")
            try:
                if url.path == "/":
                    self._send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
                    return
                if url.path == "/label":
                    self._send(HTTPStatus.OK, LABEL_PAGE.read_bytes(), "text/html; charset=utf-8")
                    return
                if url.path == "/api/profiles":
                    self._send(HTTPStatus.OK, {"profiles": [tile(p) for p in profiles.list()]})
                    return
                if url.path == "/api/session":
                    p = self._profile()
                    self._send(HTTPStatus.OK, {"profile": p and {"name": p["name"], "color": p["color"]}})
                    return
                if not url.path.startswith("/api/"):
                    asset = _static(url.path)
                    if asset:
                        self._send(HTTPStatus.OK, asset.read_bytes(), STATIC[asset.suffix])
                    else:
                        self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                if (brain := self._brain()) is None:
                    return
                if url.path == "/api/status":
                    self._send(HTTPStatus.OK, brain.status())
                elif url.path == "/api/label/next":
                    self._send(HTTPStatus.OK, brain.label_next(q))
                elif url.path == "/api/search" and q.get("q"):
                    self._send(HTTPStatus.OK, brain.search(q))
                elif url.path == "/api/beliefs":
                    self._send(HTTPStatus.OK, brain.beliefs(q))
                elif url.path == "/api/ledger":
                    self._send(HTTPStatus.OK, brain.ledger(q))
                elif url.path == "/api/ledger/questions":
                    self._send(HTTPStatus.OK, brain.questions())
                elif parts[:2] == ["api", "item"] and len(parts) == 3 and parts[2].isdigit():
                    item = brain.item(int(parts[2]))
                    self._send(HTTPStatus.OK if item else HTTPStatus.NOT_FOUND, item or {"error": "no such item"})
                elif parts[:2] == ["api", "belief"] and len(parts) == 3 and parts[2].isdigit():
                    b = brain.belief(int(parts[2]))
                    self._send(HTTPStatus.OK if b else HTTPStatus.NOT_FOUND, b or {"error": "no such belief"})
                elif url.path == "/api/graph":
                    self._send(HTTPStatus.OK, brain.graph())
                elif parts[:2] == ["api", "node"] and len(parts) == 3 and parts[2].isdigit():
                    self._send(HTTPStatus.OK, brain.item_node(int(parts[2])) or {"nodes": [], "links": []})
                elif url.path == "/api/adds":
                    self._send(HTTPStatus.OK, brain.adds_list())
                elif parts[:2] == ["api", "add"] and len(parts) == 3 and parts[2] in brain.adds:
                    self._send(HTTPStatus.OK, brain.add_state(parts[2]))
                elif parts[:2] == ["api", "act"] and len(parts) == 3 and parts[2] in brain.runs:
                    self._send(HTTPStatus.OK, brain.run_state(parts[2]))
                elif url.path == "/api/pending":
                    since = int(q["since"]) if q.get("since", "").lstrip("-").isdigit() else None
                    self._send(HTTPStatus.OK, brain.pending(since, min(float(q.get("wait", 0) or 0), 20.0)))
                elif url.path == "/api/agents":
                    self._send(HTTPStatus.OK, brain.agents())
                elif parts[:2] == ["api", "agents"] and len(parts) == 3:
                    self._send(HTTPStatus.OK, brain.agent(parts[2]))
                elif url.path == "/api/schema":
                    self._send(HTTPStatus.OK, brain.schema())
                elif parts[:2] == ["api", "schema"] and len(parts) == 3:
                    self._send(HTTPStatus.OK, brain.table(parts[2]))
                elif url.path == "/api/timeline":
                    self._send(HTTPStatus.OK, brain.timeline(q))
                elif url.path == "/api/plan":
                    self._send(HTTPStatus.OK, brain.plan(q))
                elif url.path == "/api/herald":
                    self._send(HTTPStatus.OK, brain.cards())
                elif url.path == "/api/meeting/inbox":
                    self._send(HTTPStatus.OK, brain.meeting_inbox())
                elif url.path == "/api/find":
                    self._send(HTTPStatus.OK, brain.find(q))
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except KeyError:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except Exception as e:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(e).__name__}: {e}"})

        def do_POST(self) -> None:
            if self._refuse_foreign():
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):   # forces a CORS preflight
                self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON only"})    # from any other origin
                return
            parts = urlparse(self.path).path.strip("/").split("/")
            try:
                n = int(self.headers.get("Content-Length", 0))
                if n > 1 << 20:
                    self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "at most 1 MiB"})
                    return
                body = json.loads(self.rfile.read(n) or b"{}")
                if parts == ["api", "login"]:
                    self._login(body)
                    return
                if parts == ["api", "logout"]:
                    profiles.end(self._token())
                    self._send(HTTPStatus.OK, {"ok": True}, cookie=f"{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; "
                                                                   "Max-Age=0")
                    return
                if parts == ["api", "profiles"]:
                    self._create(body)
                    return
                if (brain := self._brain()) is None:
                    return
                if parts == ["api", "ask"] and body.get("question"):
                    self._send(HTTPStatus.OK, brain.ask(body))
                elif parts == ["api", "sql"]:
                    self._send(HTTPStatus.OK, brain.sql(body))
                elif parts == ["api", "label"]:
                    self._send(HTTPStatus.OK, brain.label(body))
                elif parts == ["api", "add"] and body.get("text", "").strip():
                    self._send(HTTPStatus.OK, brain.add(body))
                elif parts == ["api", "plan"]:
                    self._send(HTTPStatus.OK, brain.replan(body))
                elif len(parts) == 3 and parts[:2] == ["api", "herald"] and parts[2].isdigit() and body.get("action"):
                    self._send(HTTPStatus.OK, brain.tap(int(parts[2]), str(body["action"])))
                elif parts == ["api", "meeting"]:
                    self._send(HTTPStatus.OK, brain.meeting(body))
                elif parts == ["api", "diplomat"]:
                    self._send(HTTPStatus.OK, brain.diplomat(body))
                elif parts == ["api", "act"] and body.get("request"):
                    self._send(HTTPStatus.OK, brain.act(body))
                elif len(parts) == 4 and parts[:2] == ["api", "act"] and parts[3] == "decide" \
                        and parts[2] in brain.runs:
                    self._send(HTTPStatus.OK, brain.decide(parts[2], body.get("approve", False)))
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except LookupError as e:
                self._send(HTTPStatus.CONFLICT, {"error": str(e)})
            except (ValueError, psycopg.Error) as e:                  # a bad request (e.g. SQL) is the user's to fix
                self._send(HTTPStatus.BAD_REQUEST, {"error": f"{type(e).__name__}: {e}".strip()})
            except Exception as e:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(e).__name__}: {e}"})

        def _session_cookie(self, token: str) -> str:
            return f"{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/"

        def _login(self, body: dict) -> None:
            name = str(body.get("profile", ""))
            try:
                token = profiles.unlock(name, str(body.get("passphrase", "")))
            except Locked as e:
                self._send(HTTPStatus.TOO_MANY_REQUESTS, {"error": str(e), "retry_after": round(e.seconds)})
                return
            except WrongPassphrase as e:
                self._send(HTTPStatus.UNAUTHORIZED, {"error": str(e), "remaining": e.remaining})
                return
            except LookupError:
                self._send(HTTPStatus.NOT_FOUND, {"error": "no such brain"})
                return
            profiles.end(self._token())                         # signing in replaces any earlier session
            p = profiles.get(name) or {}
            self._send(HTTPStatus.OK, {"profile": {"name": name, "color": p.get("color")}},
                       cookie=self._session_cookie(token))

        def _create(self, body: dict) -> None:
            """A new brain: a new database, migrated like `engram --brain NAME migrate`, and a profile for it. An
            existing database is never adopted from the page (that is `engram profile add`, on the command line)."""
            name, passphrase = str(body.get("name", "")).strip(), str(body.get("passphrase", ""))
            color = str(body.get("color") or "s1")
            try:
                profiles.check(name, passphrase, color)
            except ValueError as e:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(e)})
                return
            if profiles.get(name) is not None:
                self._send(HTTPStatus.CONFLICT, {"error": f"there is already a brain called {name}"})
                return
            if brains.exists(name):
                self._send(HTTPStatus.CONFLICT, {"error": f"a database called {name} already exists: to open it as a "
                                                          f"brain, run `engram profile add {name}` in a terminal"})
                return
            migrate(brains.url(name))
            profiles.add(name, passphrase, name, color)
            token = profiles.unlock(name, passphrase)
            profiles.end(self._token())
            self._send(HTTPStatus.OK, {"profile": {"name": name, "color": color}}, cookie=self._session_cookie(token))

    return Handler


def make_watch_handler(brain: Brain, devices: Devices) -> type[BaseHTTPRequestHandler]:
    """The watch's endpoints, and only those. Every request must come from a private address, carry no Origin (a
    browser always sends one on cross-site requests, and the watch app never does), name as its Host the address and
    port it actually reached (an IP literal, so no DNS name can be rebound onto it; this also holds when the listener
    is on all interfaces and the hotspot changes this Mac's address) and, except for hello and pairing, a paired
    device's token."""

    class Handler(BaseHTTPRequestHandler):
        timeout = 15                    # per socket read/write: a LAN client that stalls loses its thread

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

        def _send(self, status: HTTPStatus, payload: Any) -> None:
            body = json.dumps(payload, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _admit(self, pairing: bool = False) -> str | None:
            """The device name for an admitted request, '' while pairing; None once refused (already answered)."""
            local, port = self.connection.getsockname()[:2]
            if not private_peer(self.client_address[0]) or self.headers.get("Host") != f"{local}:{port}" \
                    or self.headers.get("Origin") is not None:
                self._send(HTTPStatus.FORBIDDEN, {"error": "paired watch only"})
                return None
            if pairing:
                return ""
            auth = self.headers.get("Authorization", "")
            name = devices.device(auth[7:]) if auth.startswith("Bearer ") else None
            if name is None:
                self._send(HTTPStatus.UNAUTHORIZED, {"error": "pair this watch first"})
            else:
                brain.watch_seen[name] = time.time()            # the switchboard shows the watch as present
            return name

        def _body(self, limit: int) -> bytes | None:
            n = int(self.headers.get("Content-Length") or 0)
            if n > limit:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": f"at most {limit} bytes"})
                return None
            return self.rfile.read(n)

        def do_GET(self) -> None:
            url = urlparse(self.path)
            if self._admit(pairing=url.path == "/watch/hello") is None:
                return
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/watch/hello":          # is this the Mac a watch paired with? (watch.py)
                    nonce = q.get("nonce", "")
                    if len(nonce) > 64 or not nonce.isalnum():
                        self._send(HTTPStatus.OK, {"engram": True})
                    else:
                        self._send(HTTPStatus.OK, {"engram": True, "proofs": devices.proofs(nonce)})
                elif url.path == "/watch/pending":           # approvals, and Herald's cards from every role
                    since = int(q["since"]) if q.get("since", "").lstrip("-").isdigit() else None
                    state = brain.pending(since, float(q.get("wait", LONG_POLL)))
                    try:
                        state["cards"] = brain.cards(deliver=True)
                    except psycopg.OperationalError:    # the database is down: approvals still work
                        state["cards"] = []
                    self._send(HTTPStatus.OK, state)
                else:
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            except ValueError as e:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(e)})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if (name := self._admit(pairing=path == "/watch/pair")) is None:
                return
            ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if path == "/watch/voice":
                if ctype not in ("audio/wav", "audio/x-wav", "audio/wave"):
                    self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "16-bit PCM WAV only"})
                    return
                if (wav := self._body(MAX_AUDIO)) is None:
                    return
                self._handle(lambda: _compact(brain.voice(wav)))
                return
            if ctype != "application/json":
                self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON only"})
                return
            if (raw := self._body(MAX_JSON)) is None:
                return
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                self._send(HTTPStatus.BAD_REQUEST, {"error": "bad JSON"})
                return
            if path == "/watch/pair":
                token = devices.pair(str(body.get("code", "")), str(body.get("name", "watch")))
                self._send(HTTPStatus.OK if token else HTTPStatus.FORBIDDEN,
                           {"token": token} if token else {"error": "wrong or expired code"})
            elif path == "/watch/card" and str(body.get("id", "")).isdigit() and body.get("action"):
                self._handle(lambda: brain.card(int(body["id"]), str(body["action"]), f"watch:{name}"))
            elif path == "/watch/decide" and body.get("run") in brain.runs:
                self._handle(lambda: brain.decide(body["run"], body.get("approve") is True, f"watch:{name}"))
            elif path == "/watch/ask" and str(body.get("question", "")).strip():
                self._handle(lambda: _compact({"kind": "ask", **brain.ask({"question": body["question"]})}))
            elif path == "/watch/add" and str(body.get("text", "")).strip():
                self._handle(lambda: brain.add({"text": body["text"], "title": body.get("title") or "Watch note",
                                                "remember": True}))
            else:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def _handle(self, call: Any) -> None:
            try:
                self._send(HTTPStatus.OK, call())
            except PermissionError as e:
                self._send(HTTPStatus.FORBIDDEN, {"error": str(e)})
            except LookupError as e:
                self._send(HTTPStatus.CONFLICT, {"error": str(e)})
            except Unavailable as e:
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(e)})
            except ValueError as e:
                self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(e)})
            except Exception as e:
                self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(e).__name__}: {e}"})

    return Handler


def serve(settings: Settings, port: int, lan: tuple[str, int] | None = None) -> None:
    """Serve on 127.0.0.1 until interrupted, and the watch on `lan` (address, port) when given, announced over mDNS;
    inside the WorkBench sandbox when its clone is present. The watch reaches the brain `settings` names."""
    workbench = (settings.workbench_dir / "src" / "tools" / "toolkits.py").exists()
    brains = Brains(settings, workbench)
    default = brains.get(conninfo_to_dict(settings.database_url)["dbname"])
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(brains, hosts, Profiles(settings.profiles_file)))
    watch = announce = None
    default.start_herald()                              # Herald posts cards to the watch's brain
    if lan:
        default.lan = True
        watch = ThreadingHTTPServer(lan, make_watch_handler(default, Devices(settings.watch_file)))
        threading.Thread(target=watch.serve_forever, daemon=True).start()
        announce = advertise(lan[1], f"engram {settings.database_url.rsplit('/', 1)[-1]}")
    try:
        if workbench:
            with wb.sandbox(settings.workbench_dir):
                server.serve_forever()
        else:
            server.serve_forever()
    finally:
        if announce:
            announce.terminate()
        if watch:
            watch.shutdown()
            watch.server_close()
        server.server_close()
        brains.close()


def _compact(r: dict) -> dict:
    """An answer sized for a watch screen: the text, who answered, and one line per cited item."""
    if r.get("kind") != "ask":
        return r
    return {k: r[k] for k in ("heard", "kind", "heard_ms", "answer", "answered_by", "seconds") if k in r} | {
        "cites": [f"{c['date'] or ''} {c['subject'] or '(no subject)'}".strip() for c in r["cites"][:3]]}


def _verdict(v: Verdict | None) -> dict | None:
    return None if v is None else {"value": v.value, "p": round(v.p, 3), "p_yes": round(v.probs.get("yes", 0), 3),
                                   "settled": v.settled, "tier": v.tier}


def _role_step(x) -> dict:
    """A meeting-pipeline step in the shape the page shows agent steps in: the role, and what it did."""
    return {"tool": x.role, "args": {}, "ran": True, "observation": x.what, "gate": None, "ms": x.ms}


def _step(s: agent.Step) -> dict:
    c = s.check
    return {"tool": s.tool, "args": s.args, "ran": s.ran, "observation": s.observation[:500],
            "gate": None if c is None else {"reason": c.reason, "tier": c.tier, "judge": _verdict(c.verdict)}}


def _date(d: datetime | None) -> str | None:
    return None if d is None else f"{d:%Y-%m-%d}"


def _day(s: str | None) -> datetime | None:
    return datetime.strptime(s, "%Y-%m-%d") if s else None


def _graph(people: list[str], items: list[dict], beliefs: list[dict], people_from_items: bool = False) -> dict:
    nodes: dict[str, dict] = {"owner": {"id": "owner", "type": "owner", "label": "you", "val": 14}}
    links: list[dict] = []
    known = set(people)

    def person(addr: str) -> str | None:
        if addr in known or (people_from_items and "@" in addr):
            nid = f"p:{addr}"
            nodes.setdefault(nid, {"id": nid, "type": "person", "label": addr.split("@")[0].replace(".", " "),
                                   "addr": addr, "val": 3})
            return nid
        return None

    for a in people:
        person(a)
    for it in items:
        nid = f"i:{it['id']}"
        nodes[nid] = {"id": nid, "type": "item", "item": it["id"], "kind": it["kind"], "label": it["subject"] or
                      "(no subject)", "date": _date(it["sent_at"]), "val": 1}
        if it["direction"] == "out":
            links.append({"source": "owner", "target": nid})
            links += [{"source": nid, "target": t} for t in map(person, it["to_addrs"][:6]) if t]
        else:
            sender = person(it["from_addr"])
            links.append({"source": sender or "owner", "target": nid})
    by_name = {n["label"]: nid for nid, n in nodes.items() if n["type"] == "person"}
    for b in beliefs:
        nid = f"b:{b['id']}"
        nodes[nid] = {"id": nid, "type": "belief", "belief": b["id"], "kind": b["kind"], "label": b["statement"],
                      "author": b["author"], "status": b["status"], "val": 2}
        if f"i:{b['item_id']}" in nodes:
            links.append({"source": f"i:{b['item_id']}", "target": nid})
        for who in (b["actor"], b["other"]):
            target = by_name.get((who or "").strip().lower())
            if target:
                links.append({"source": nid, "target": target})
    degree: dict[str, int] = {}
    for link in links:
        for end in (link["source"], link["target"]):
            degree[end] = degree.get(end, 0) + 1
    for nid, n in nodes.items():
        if n["type"] == "person":
            n["val"] = 2 + min(degree.get(nid, 0), 30) / 3
    return {"nodes": [n for nid, n in nodes.items() if n["type"] != "person" or degree.get(nid)], "links": links}


def _cell(v: Any) -> Any:
    return v if isinstance(v, (int, float, str, bool)) or v is None else str(v)


def _static(path: str) -> Path | None:
    """A script, stylesheet, font or icon inside web/, and nothing outside it (no `..` escapes)."""
    root = WEB.resolve()
    target = (WEB / path.lstrip("/")).resolve()
    return target if target.is_relative_to(root) and target.is_file() and target.suffix in STATIC else None


def _ago(seconds: float) -> str:
    return f"{seconds:.0f} s" if seconds < 90 else f"{seconds / 60:.0f} min" if seconds < 5400 else \
        f"{seconds / 3600:.0f} h"


def _short(v: Any) -> Any:
    """A table cell for the sample view: long text and vectors cut short."""
    v = _cell(v)
    return v[:160] + "…" if isinstance(v, str) and len(v) > 160 else v
