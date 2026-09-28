"""The brain as tools for AI agents (docs/research/handoff-round3-agent-queries.md, W1).

Small tools with clear parameters, after OpenJarvis's agent surface, running on engram's engines: tuned hybrid search
collapsed to one hit per conversation, reading within a token budget with the thread around a hit, structured
beliefs (untrusted ones never served), people as entities, read-only SQL as a role that can only read, a recall
sweep by the small judge (~0.2 s an item, where OpenJarvis's `scan_chunks` spends LLM calls), a fact check, and
`answer`, which ends a run with citations as record ids rather than text to be parsed back. Every result carries
ids; every result fits a budget. The same functions back the MCP server (mcp.py) and the local test agent."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from psycopg.conninfo import make_conninfo

from . import index, people
from .act import Tool
from .db import connect
from .judge import Judge
from .labels import relevant_question, supported_question

CHARS_PER_TOKEN = 4
SNIPPET = 300


@dataclass
class Brain:
    url: str
    embed: Callable[[list[str]], list[list[float]]] | None = None     # None: keyword search only
    judge_factory: Callable[[], Judge] | None = None                    # for scan and check, made on first use
    ask_fn: Callable[[str], dict] | None = None                         # the full `ask` pipeline, if offered
    answers: list[dict] = field(default_factory=list)                   # what `answer` recorded
    seen: dict[int, str] = field(default_factory=dict)                  # ids the tools showed this run -> subject
    question: str = ""                                                  # the run's question, for checking answers
    refused: int = 0
    _judge: Judge | None = None

    @property
    def judge(self) -> Judge | None:
        if self._judge is None and self.judge_factory is not None:
            self._judge = self.judge_factory()
        return self._judge

    # ------------------------------------------------------------------------------------------ finding
    def search(self, query: str, person: str = "", since: str = "", until: str = "", direction: str = "",
               k: int = 8, cursor: int = 0) -> dict:
        with connect(self.url) as conn:
            who = self._addresses(conn, person) if person else ()
            hits = index.search(conn, self.embed, query, (cursor + k) * 3, since=_day(since), until=_day(until),
                                people=who, direction=direction or None)
            meta = {r["id"]: r for r in conn.execute(
                "SELECT i.id, i.thread_key, i.to_addrs, (SELECT count(*) FROM items t "
                "WHERE t.thread_key = i.thread_key AND i.thread_key <> '') AS n FROM items i WHERE i.id = ANY(%s)",
                ([h.item_id for h in hits],))}
        seen, out = set(), []
        for h in hits:                                  # one hit per conversation, its best
            thread = meta[h.item_id]["thread_key"] or f"item:{h.item_id}"
            if thread in seen:
                continue
            seen.add(thread)
            out.append({"id": h.item_id, "date": _date(h.sent_at), "from": h.from_addr,
                        "to": meta[h.item_id]["to_addrs"][:3], "subject": h.subject,
                        "thread_items": max(1, meta[h.item_id]["n"]), "why": h.why,
                        "snippet": _snippet(h.text, query)})
        page = out[cursor:cursor + k]
        self.seen |= {r["id"]: r["subject"] for r in page}
        return {"results": page, "next_cursor": cursor + k if len(out) > cursor + k else None}

    def read(self, ids: list[int], budget_tokens: int = 1500, thread: bool = False) -> dict:
        budget = max(200, budget_tokens) * CHARS_PER_TOKEN
        with connect(self.url) as conn:
            wanted = [int(i) for i in ids][:10]
            rows = {r["id"]: r for r in conn.execute(
                "SELECT id, sent_at, from_addr, subject, body, quoted, thread_key FROM items WHERE id = ANY(%s)",
                (wanted,))}
            order = [i for i in wanted if i in rows]
            if thread:                                  # the conversation around each item, oldest first
                keys = [rows[i]["thread_key"] for i in order if rows[i]["thread_key"]]
                for r in conn.execute("SELECT id, sent_at, from_addr, subject, body, quoted, thread_key FROM items "
                                      "WHERE thread_key = ANY(%s) ORDER BY sent_at LIMIT 20", (keys,)):
                    if r["id"] not in rows:
                        rows[r["id"]] = r
                        order.append(r["id"])
        order, omitted = order[:budget // SNIPPET], order[budget // SNIPPET:]  # at least a snippet each, asked first
        out, left = [], budget
        for i in order:
            r = rows[i]
            text = r["body"] + (f"\n\n[quoted]\n{r['quoted']}" if r["quoted"] and len(r["body"]) < 400 else "")
            share = min(len(text), left // (len(order) - len(out)))  # what shorter items leave goes to the rest
            out.append({"id": i, "date": _date(r["sent_at"]), "from": r["from_addr"], "subject": r["subject"],
                        "text": text[:share], "truncated": len(text) > share})
            left -= share
        self.seen |= {o["id"]: o["subject"] for o in out}
        return {"items": out, "omitted_ids": omitted}

    def beliefs(self, kind: str = "", person: str = "", status: str = "", due_after: str = "", due_before: str = "",
                k: int = 20) -> dict:
        with connect(self.url) as conn:
            names = self._names(conn, person) if person else []
            rows = conn.execute(
                "SELECT id, kind, actor, other, statement, due_at, status, quote, item_id, author, trust, sent_at "
                "FROM current_beliefs WHERE trust <> 'quarantined' "
                "AND (%(kind)s = '' OR kind = %(kind)s) AND (%(status)s = '' OR status = %(status)s) "
                "AND (%(n)s::text[] IS NULL OR actor LIKE ANY(%(n)s) OR other LIKE ANY(%(n)s)) "
                "AND (%(a)s::timestamptz IS NULL OR due_at >= %(a)s) "
                "AND (%(b)s::timestamptz IS NULL OR due_at < %(b)s) "
                "ORDER BY coalesce(due_at, sent_at) DESC NULLS LAST LIMIT %(k)s",
                {"kind": kind, "status": status, "n": [f"%{index._like_literal(n)}%" for n in names] or None,
                 "a": _day(due_after), "b": _day(due_before), "k": min(k, 50)}).fetchall()
        self.seen |= {r["item_id"]: r["statement"] for r in rows}
        return {"beliefs": [{"id": r["id"], "kind": r["kind"], "actor": r["actor"], "other": r["other"],
                             "statement": r["statement"], "due": r["due_at"].isoformat() if r["due_at"] else None,
                             "status": r["status"], "said": _date(r["sent_at"]), "quote": r["quote"][:200],
                             "source_id": r["item_id"], "author": r["author"], "trust": r["trust"]} for r in rows]}

    def people(self, name: str) -> dict:
        with connect(self.url) as conn:
            return {"people": [{"name": r["name"], "addresses": r["addresses"][:6], "aliases": r["aliases"][:6],
                                "items": r["n_items"]} for r in people.find(conn, name)]}

    def sql(self, sql: str, max_rows: int = 100) -> dict:
        """One read-only statement as `engram_reader` (not a superuser: sql/009), 3 s, at most `max_rows`."""
        statement = sql.strip().rstrip(";")
        if not statement or ";" in statement:
            raise ValueError("one statement, please")
        reader = make_conninfo(self.url, user="engram_reader", password="engram_reader")
        with connect(reader) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '3s'")
            cur = conn.execute(statement)
            cols = [d.name for d in cur.description or []]
            rows = cur.fetchmany(max_rows + 1)
            conn.rollback()
        return {"columns": cols, "rows": [[_cell(r[c]) for c in cols] for r in rows[:max_rows]],
                "truncated": len(rows) > max_rows}

    # ---------------------------------------------------------------------------------------- judging
    def scan(self, question: str, person: str = "", since: str = "", until: str = "", max_items: int = 40) -> dict:
        """Ask the small judge `relevant` of every item a filter selects: recall where search ranking fails."""
        if self.judge is None or self.judge.s1 is None:
            raise LookupError("scan needs the small judge")
        with connect(self.url) as conn:
            who = self._addresses(conn, person) if person else None
            rows = conn.execute(
                "SELECT id, sent_at, from_addr, subject, body, quoted FROM items WHERE length(body) > 20 "
                "AND (%(w)s::text[] IS NULL OR from_addr = ANY(%(w)s) OR to_addrs && %(w)s) "
                "AND (%(s)s::timestamptz IS NULL OR sent_at >= %(s)s) "
                "AND (%(u)s::timestamptz IS NULL OR sent_at < %(u)s) "
                "ORDER BY sent_at DESC NULLS LAST LIMIT %(k)s",
                {"w": list(who) if who else None, "s": _day(since), "u": _day(until),
                 "k": min(max_items, 200)}).fetchall()
        found = []
        for r in rows:
            a = self.judge.answer("S1", self.judge.s1, relevant_question(question), _text(r), f"item:{r['id']}|scan")
            p = a.probs.get("yes", 0.0) if a.logprobs else 0.0
            if p >= 0.5:
                found.append({"id": r["id"], "date": _date(r["sent_at"]), "from": r["from_addr"],
                              "subject": r["subject"], "p_relevant": round(p, 2),
                              "snippet": " ".join(r["body"].split())[:SNIPPET]})
        self.seen |= {f["id"]: f["subject"] for f in found}
        return {"scanned": len(rows), "relevant": sorted(found, key=lambda f: -f["p_relevant"])[:15]}

    def check(self, question: str, claim: str, ids: list[int]) -> dict:
        """Does any of these items support the claim as an answer to the question? The fine-tuned `supported` judge."""
        if self.judge is None:
            raise LookupError("check needs the judge")
        with connect(self.url) as conn:
            texts = {r["id"]: _text(r) for r in conn.execute(
                "SELECT id, subject, from_addr, body, quoted FROM items WHERE id = ANY(%s)",
                ([int(i) for i in ids][:5],))}
        verdicts = {i: self.judge.ask(supported_question(question, claim), t, f"item:{i}|check")
                    for i, t in texts.items()}
        if not verdicts:
            return {"supported": False, "p": 0.0, "settled": False, "by": None, "note": "no such items"}
        i, v = max(verdicts.items(), key=lambda kv: kv[1].probs.get("yes", 0.0))
        return {"supported": v.value == "yes", "p": round(v.probs.get("yes", 0.0), 3), "settled": v.settled,
                "by": i, "tier": v.tier}

    def ask(self, question: str) -> dict:
        if self.ask_fn is None:
            raise LookupError("ask is not offered here")
        return self.ask_fn(question)

    def begin(self, question: str = "") -> None:
        """A new run: citations must come from what this run's tools return."""
        self.seen, self.question, self.refused = {}, question, 0

    def answer(self, answer: str, cited_ids: list[int] | None = None, question: str = "") -> dict:
        """Record the run's answer and end the run (the next one starts with nothing seen)."""
        cited = [int(i) for i in cited_ids or []]
        self.question = question or self.question
        unseen = [i for i in cited if i not in self.seen]
        if unseen:                                      # a citation must be a record a tool actually returned
            menu = "; ".join(f"{i}: {subject[:60]}" for i, subject in list(self.seen.items())[:12])
            raise ValueError(f"ids {unseen} were never returned by a tool. Cite from these: {menu}")
        support = self._support(answer, cited)
        if support and not any(support.values()) and self.refused < 1:  # System 1 checks the citations, once
            self.refused += 1
            menu = "; ".join(f"{i}: {subject[:60]}" for i, subject in list(self.seen.items())[:12])
            raise ValueError(f"none of {cited} supports that answer, per the judge. Cite the item that says it, "
                             f"from: {menu}")
        supported = [i for i, ok in support.items() if ok]
        self.answers.append({"answer": answer, "cited_ids": cited, "supported_ids": supported})
        self.begin()
        return {"recorded": True, "supported_ids": supported}

    def _support(self, answer: str, cited: list[int]) -> dict[int, bool]:
        if not (self.question and cited and self.judge):
            return {}
        return {i: self.check(self.question, answer, [i])["supported"] for i in cited}

    # ------------------------------------------------------------------------------------------ helpers
    def _addresses(self, conn: Any, person: str) -> tuple[str, ...]:
        found = people.find(conn, person, 1)
        return tuple(found[0]["addresses"]) if found else (person.lower(),)

    def _names(self, conn: Any, person: str) -> list[str]:
        found = people.find(conn, person, 1)
        if not found:
            return [person.lower()]
        name = found[0]["name"].lower()
        first = name.split()[0]                         # beliefs often use just a first name ("shirley")
        shared = conn.execute("SELECT count(*) AS n FROM people WHERE key LIKE %s",
                              (index._like_literal(first) + " %",)).fetchone()["n"]
        return sorted({*found[0]["aliases"], name, *found[0]["addresses"], *([first] if shared == 1 else [])}
                      - {"me", "owner"})


# ---------------------------------------------------------------------------------------------- schemas

def _p(**props: dict) -> dict:
    clean = {k: {a: b for a, b in v.items() if a != "required"} for k, v in props.items()}
    return {"type": "object", "properties": clean, "required": [k for k, v in props.items() if v.get("required")]}


S, N, A = {"type": "string"}, {"type": "integer"}, {"type": "array", "items": {"type": "integer"}}
SPECS: dict[str, tuple[str, dict]] = {
    "brain_search": ("Find items (emails, notes) by keywords or meaning. One result per conversation, newest "
                     "evidence first; snippets only. Filters: person (name or address), since/until (YYYY-MM-DD), "
                     "direction ('in' received, 'out' sent). ~50 ms. Use brain_read for full text.",
                     _p(query={**S, "required": True}, person=S, since=S, until=S, direction=S, k=N, cursor=N)),
    "brain_read": ("Full text of items by id, within a token budget; thread=true adds the rest of each "
                   "conversation. ~10 ms.", _p(ids={**A, "required": True}, budget_tokens=N,
                                               thread={"type": "boolean"})),
    "brain_beliefs": ("What the owner's memory holds: commitments, decisions and meetings, each with who, when, "
                      "status and a verbatim quote from its source. Filters: kind, person, status (open/done/"
                      "dropped), due_after/due_before (YYYY-MM-DD). ~5 ms. Best for 'what did X promise/decide'.",
                      _p(kind=S, person=S, status=S, due_after=S, due_before=S, k=N)),
    "brain_people": ("Who someone is: their name, every address and alias, how often they write. ~5 ms.",
                     _p(name={**S, "required": True})),
    "brain_sql": ("One read-only SQL statement over the brain (Postgres). Tables: items(id, sent_at, from_addr, "
                  "to_addrs text[], subject, body, thread_key, direction 'in'|'out'), current_beliefs(kind, actor, "
                  "other, statement, due_at, status, trust, item_id), people(name, addresses, aliases, n_items), "
                  "judgements. Best for counts, dates and lists. 3 s limit, 100 rows.",
                  _p(sql={**S, "required": True})),
    "brain_scan": ("Recall sweep: the small judge reads every item a filter selects (person, since, until; "
                   "newest first, at most max_items) and returns those that hold the answer. ~0.2 s per item: use "
                   "when search misses, with a tight filter.",
                   _p(question={**S, "required": True}, person=S, since=S, until=S, max_items=N)),
    "brain_check": ("Check a claim against items before relying on it: does any of these items support the claim "
                    "as an answer to the question? The owner's fine-tuned judge, ~0.2 s per item.",
                    _p(question={**S, "required": True}, claim={**S, "required": True}, ids={**A, "required": True})),
    "brain_ask": ("One-call answer: search, judge, answer with citations and a verdict. ~2-11 s.",
                  _p(question={**S, "required": True})),
    "answer": ("Give the final answer. cited_ids: the ids of the items it rests on, from this run's tool results. "
               "question: the request being answered (the owner's judge then checks the citations support it). "
               "Call exactly once, last: it ends the run.",
               _p(answer={**S, "required": True}, cited_ids=A, question=S)),
}


def tools(brain: Brain, names: tuple[str, ...] | None = None) -> list[Tool]:
    """The tools as engram `Tool`s (effect 'read': the gate lets reads through), results as JSON text."""
    fns = {"brain_search": brain.search, "brain_read": brain.read, "brain_beliefs": brain.beliefs,
           "brain_people": brain.people, "brain_sql": brain.sql, "brain_scan": brain.scan, "brain_check": brain.check,
           "brain_ask": brain.ask, "answer": brain.answer}
    out = []
    for name, (desc, params) in SPECS.items():
        if names is None or name in names:
            fn = fns[name]
            out.append(Tool(name, "read", lambda fn=fn, **kw: json.dumps(fn(**kw), default=str), desc,
                            json.loads(json.dumps(params))))
    return out


def _text(r: dict) -> str:
    """An item as the judge was trained to read it (labels.item_texts)."""
    return f"Subject: {r['subject']}\nFrom: {r['from_addr']}\n\n{r['body']}\n\n{r['quoted']}".strip()


def _snippet(text: str, query: str) -> str:
    """The SNIPPET characters of `text` where most of the query's words are (by a 5-letter stem): the passage that
    matched rather than the chunk's opening, so an agent can tell from the snippet whether to read on."""
    words = " ".join(text.split())
    stems = {w[:5] for w in re.findall(r"[a-z0-9$]{4,}", query.lower())}
    if len(words) <= SNIPPET or not stems:
        return words[:SNIPPET]
    starts = [0, *(m.end() for m in re.finditer(r"[.!?]\s|\s", words))]
    hits = [(m.start(), m.group()[:5]) for m in re.finditer(r"[a-z0-9$]{4,}", words.lower())]
    best, at = -1, 0
    for s0 in starts[::3]:
        n = len({w for i, w in hits if s0 <= i < s0 + SNIPPET and w in stems})
        if n > best:
            best, at = n, s0
    first = min((i for i, w in hits if at <= i < at + SNIPPET and w in stems), default=at)
    at = max((x for x in starts if x <= max(at, first - 60)), default=0)  # a little context before the match
    return ("…" if at else "") + words[at:at + SNIPPET]


def _day(s: str | None) -> datetime | None:
    return datetime.strptime(s, "%Y-%m-%d") if s else None


def _date(d: datetime | None) -> str | None:
    return None if d is None else f"{d:%Y-%m-%d}"


def _cell(v: Any) -> Any:
    return v if isinstance(v, (int, float, str, bool)) or v is None else str(v)
