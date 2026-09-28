"""Derived labels for adapter v2 (docs/research/agent-roster-review.md §6): the four new decisions get labels from
structure the brain already has, not from a teacher model, and the owner's team checks each once on the labelling
page (`/label`). A human label beats the derived one; the agreement between them is itself reported.

- `remember`: yes when the memory build extracted a quote-verified belief from the item; no when S0's bulk rules
  drop it, or the build read it and found nothing.
- `meeting_request`: yes when the item gave a meeting belief; no when it gave only commitments or decisions (a hard
  negative), or is bulk mail.
- `fulfilled`: an open commitment and a later message in its thread; yes when the actor sends it and it reads as
  delivery ("attached", "here is", "done"...), else no. Such pairs are rare, so near misses (only one of the two)
  are queued too, for the team to find the fulfilments the rule misses.
- `todo` (Planner): the owner's commitments. No structure says which are real to-dos, so there is no derived label:
  it trains on the team's checks alone.
- `contradicts`: a belief and the one that superseded it; yes when the time changed (both cannot hold), no when it
  is a restatement; plus pairs of unrelated beliefs about the same person, no.

The 90 items hand-labelled for `remember` (data/results/remember-gold.json) stay evaluation-only: they are never
queued here, so they never reach training."""
from __future__ import annotations

import json
import random
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import psycopg

from .judge import Question
from .labels import Example
from .memory import (
    CONTRADICTS,
    FULFILLED,
    MEETING,
    REMEMBER,
    bulk,
    contradict_state,
    fulfil_state,
    party_names,
    reading_text,
)
from .planner import TODO, owner_names, todo_state

QUESTIONS: dict[str, Question] = {q.name: q for q in (REMEMBER, MEETING, FULFILLED, CONTRADICTS, TODO)}
DELIVERY = re.compile(r"\battach(ed|ment)\b|\benclos(ed|ing)\b|\bhere (is|are)\b|\bhere's\b|\bplease find\b|"
                      r"\bas promised\b|\b(i|we) (have )?(sent|done|finished|completed|booked|forwarded)\b|"
                      r"\bi'?ve (sent|done|finished|completed|booked|forwarded)\b", re.I)
ITEM = "SELECT id, subject, from_addr, body, quoted, thread_key FROM items WHERE id = ANY(%s)"


def gold_items(path: Path) -> set[int]:
    """Items hand-labelled as the `remember` evaluation set: never used for training."""
    if not path.exists():
        return set()
    d = json.loads(path.read_text())
    return {int(i) for part in ("dev", "test") for i in d.get(part, {})}


def queue(conn: psycopg.Connection, n: int, rng: random.Random, gold: set[int] = frozenset(),
          mailbox: str = "") -> dict[str, int]:
    """Derive up to `n` balanced examples per decision and store them (material + derived label). Idempotent:
    examples already queued keep their material and labels. Returns how many were added per decision."""
    added = {}
    for name, rows in (("remember", _remember(conn, n, rng, gold)), ("meeting_request", _meeting(conn, n, rng, gold)),
                       ("fulfilled", _fulfilled(conn, n, rng)), ("contradicts", _contradicts(conn, n, rng)),
                       ("todo", _todo(conn, n, rng, mailbox))):
        k = 0
        for subject, state, grp, value in rows:
            k += conn.execute("INSERT INTO label_examples (question, subject, state, grp) VALUES (%s, %s, %s, %s) "
                              "ON CONFLICT DO NOTHING", (name, subject, state, grp)).rowcount
            if value is not None:                   # todo: the team's label only
                conn.execute("INSERT INTO labels (question, subject, value, source) VALUES (%s, %s, %s, "
                             "'derived') ON CONFLICT DO NOTHING", (name, subject, value))
        added[name] = k
    conn.commit()
    return added


def examples(conn: psycopg.Connection, name: str, human_only: bool = False) -> list[Example]:
    """The queued examples of one decision: the team's check where there is one, else the assistant's, else the
    derived label. A skip (unclear) keeps the example out. `human_only`: checked examples only (team or
    assistant), each keeping its source."""
    q = QUESTIONS[name]
    rows = conn.execute(
        "SELECT e.subject, e.state, e.grp, coalesce(h.value, a.value, d.value) AS value, "
        "CASE WHEN h.value IS NOT NULL THEN 'human' WHEN a.value IS NOT NULL THEN 'assistant' ELSE 'derived' END "
        "AS source FROM label_examples e "
        "LEFT JOIN labels h ON h.question = e.question AND h.subject = e.subject AND h.source = 'human' "
        "LEFT JOIN labels a ON a.question = e.question AND a.subject = e.subject AND a.source = 'assistant' "
        "LEFT JOIN labels d ON d.question = e.question AND d.subject = e.subject AND d.source = 'derived' "
        "WHERE e.question = %s AND coalesce(h.value, a.value, d.value) IN ('yes', 'no') ORDER BY e.subject",
        (name,)).fetchall()
    return [Example(q, r["state"], r["subject"], r["value"], r["source"], r["grp"]) for r in rows
            if not human_only or r["source"] != "derived"]


def agreement(conn: psycopg.Connection) -> dict[str, dict[str, Any]]:
    """Per decision: how many the team checked, and how often the derived label was right."""
    out = {}
    for r in conn.execute(
            "SELECT e.question, count(h.value) AS checked, count(*) FILTER (WHERE h.value = d.value) AS agree, "
            "count(*) FILTER (WHERE h.value = 'skip') AS skipped, count(*) AS queued, "
            "count(*) FILTER (WHERE h.value IN ('yes', 'no') AND d.value IS NOT NULL) AS comparable "
            "FROM label_examples e "
            "LEFT JOIN LATERAL (SELECT value FROM labels l WHERE l.question = e.question AND l.subject = e.subject "
            "AND l.source IN ('human', 'assistant') ORDER BY l.source = 'human' DESC LIMIT 1) h ON true "
            "LEFT JOIN labels d ON d.question = e.question AND d.subject = e.subject AND d.source = 'derived' "
            "GROUP BY e.question ORDER BY e.question"):
        out[r["question"]] = {"queued": r["queued"], "checked": r["checked"], "skipped": r["skipped"],
                              "derived_right": round(r["agree"] / r["comparable"], 3) if r["comparable"] else None}
    return out


def next_to_check(conn: psycopg.Connection, name: str) -> dict[str, Any] | None:
    """One example of `name` the team has not checked yet (a stable random order), with its derived label."""
    r = conn.execute(
        "SELECT e.subject, e.state, d.value AS derived FROM label_examples e LEFT JOIN labels d ON "
        "d.question = e.question AND d.subject = e.subject AND d.source = 'derived' WHERE e.question = %s AND NOT "
        "EXISTS (SELECT 1 FROM labels h WHERE h.question = e.question AND h.subject = e.subject AND "
        "h.source = 'human') ORDER BY md5(e.subject) LIMIT 1", (name,)).fetchone()
    if r is None:
        return None
    return {"question": name, "instructions": QUESTIONS[name].instructions, **r}


def check(conn: psycopg.Connection, name: str, subject: str, value: str) -> None:
    """The team's verdict on one queued example: yes, no, or skip (unclear: kept out of training)."""
    if name not in QUESTIONS or value not in ("yes", "no", "skip"):
        raise ValueError("unknown decision or verdict")
    if not conn.execute("SELECT 1 FROM label_examples WHERE question = %s AND subject = %s", (name, subject)
                        ).fetchone():
        raise LookupError("no such example")
    conn.execute("INSERT INTO labels (question, subject, value, source) VALUES (%s, %s, %s, 'human') "
                 "ON CONFLICT (question, subject, source) DO UPDATE SET value = EXCLUDED.value, created_at = now()",
                 (name, subject, value))
    conn.commit()


def owner_verdict(conn: psycopg.Connection, name: str, belief: int, value: str, item: int | None = None,
                  new_belief: int | None = None) -> str:
    """The owner's verdict on a `fulfilled` (belief, item) or `contradicts` (belief, new belief) finding, given
    anywhere (the watch, the page): a human label plus the exact material the judge read, so it trains adapter v2
    like a checked example. Returns the subject. The caller commits."""
    if value not in ("yes", "no"):
        raise ValueError("verdict must be yes or no")
    cols = "b.id, b.kind, b.actor, b.other, b.statement, b.when_text, i.thread_key, i.id AS item"
    old = conn.execute(f"SELECT {cols} FROM beliefs b JOIN items i ON i.id = b.item_id WHERE b.id = %s",
                       (belief,)).fetchone()
    if old is None:
        raise LookupError("no such belief")
    if name == "fulfilled" and item is not None:
        r = conn.execute(ITEM, ([item],)).fetchone()
        if r is None:
            raise LookupError("no such item")
        subject, state, grp = f"belief:{belief}|item:{item}", fulfil_state(old, reading_text(r)), _group(r)
    elif name == "contradicts" and new_belief is not None:
        new = conn.execute(f"SELECT {cols} FROM beliefs b JOIN items i ON i.id = b.item_id WHERE b.id = %s",
                           (new_belief,)).fetchone()
        if new is None:
            raise LookupError("no such belief")
        subject, state = f"belief:{belief}|belief:{new_belief}", contradict_state(old, new)
        grp = _group({"thread_key": old["thread_key"], "id": old["item"]})
    else:
        raise ValueError("fulfilled needs an item, contradicts a new belief")
    conn.execute("INSERT INTO label_examples (question, subject, state, grp) VALUES (%s, %s, %s, %s) "
                 "ON CONFLICT DO NOTHING", (name, subject, state, grp))
    conn.execute("INSERT INTO labels (question, subject, value, source) VALUES (%s, %s, %s, 'human') "
                 "ON CONFLICT (question, subject, source) DO UPDATE SET value = EXCLUDED.value, created_at = now()",
                 (name, subject, value))
    return subject


# ------------------------------------------------------------------------------------------------ derivations

Row = tuple[str, str, str, str | None]      # subject, state, group, derived label (None: team only)


def _items(conn: psycopg.Connection, ids: Sequence[int]) -> dict[int, dict[str, Any]]:
    return {r["id"]: r for r in conn.execute(ITEM, (list(ids),))}


def _group(r: dict[str, Any]) -> str:
    return f"thread:{r['thread_key']}" if r["thread_key"] else f"item:{r['id']}"


def _balanced(yes: list[int], no: list[int], n: int, rng: random.Random) -> list[tuple[int, str]]:
    k = min(n // 2, len(yes), len(no))
    return [(i, "yes") for i in rng.sample(yes, k)] + [(i, "no") for i in rng.sample(no, k)]


def _item_rows(conn: psycopg.Connection, picked: list[tuple[int, str]]) -> list[Row]:
    items = _items(conn, [i for i, _ in picked])
    return [(f"item:{i}", reading_text(items[i]), _group(items[i]), v) for i, v in picked if i in items]


def _bulk_ids(conn: psycopg.Connection, n: int, gold: set[int]) -> list[int]:
    """Up to n items S0's bulk rules drop, from a random sample of all items."""
    ids = [r["id"] for r in conn.execute("SELECT id FROM items WHERE length(body) > 20 AND kind <> 'meeting' "
                                         "ORDER BY md5(id::text) LIMIT %s", (n * 20,))]
    items = _items(conn, ids)
    return [i for i in ids if i in items and i not in gold and bulk(items[i])][:n]


def _remember(conn: psycopg.Connection, n: int, rng: random.Random, gold: set[int]) -> list[Row]:
    scans = conn.execute("SELECT item_id, kinds FROM memory_scans").fetchall()
    yes = [r["item_id"] for r in scans if r["kinds"] and r["item_id"] not in gold]
    empty = [r["item_id"] for r in scans if not r["kinds"] and r["item_id"] not in gold]
    bulk_ids = _bulk_ids(conn, n // 4, gold)
    no = [*bulk_ids, *rng.sample(empty, min(len(empty), n // 2 - len(bulk_ids)))]
    return _item_rows(conn, _balanced(yes, no, n, rng))


def _meeting(conn: psycopg.Connection, n: int, rng: random.Random, gold: set[int]) -> list[Row]:
    kinds = {r["item_id"]: set(r["k"]) for r in
             conn.execute("SELECT item_id, array_agg(DISTINCT kind) AS k FROM beliefs GROUP BY item_id")}
    yes = [i for i, k in kinds.items() if "meeting" in k and i not in gold]
    hard = [i for i, k in kinds.items() if "meeting" not in k and i not in gold]
    bulk_ids = _bulk_ids(conn, n // 6, gold)
    no = [*bulk_ids, *rng.sample(hard, min(len(hard), n // 2 - len(bulk_ids)))]
    return _item_rows(conn, _balanced(yes, no, n, rng))


def _fulfilled(conn: psycopg.Connection, n: int, rng: random.Random) -> list[Row]:
    pairs = conn.execute(
        "SELECT b.id, b.actor, b.other, b.statement, b.when_text, i.id AS item FROM beliefs b "
        "JOIN items s ON s.id = b.item_id JOIN items i ON i.thread_key = s.thread_key AND i.id <> s.id "
        "AND COALESCE(i.sent_at > s.sent_at, i.id > s.id) "
        "WHERE b.kind = 'commitment' AND b.trust <> 'quarantined' AND s.thread_key <> '' AND length(i.body) > 20 "
        "ORDER BY b.id, i.sent_at LIMIT 5000").fetchall()
    items = _items(conn, list({p["item"] for p in pairs}))
    senders = {r["a"]: {r["key"], *r["aliases"]} for r in
               conn.execute("SELECT unnest(addresses) AS a, key, aliases FROM people")}
    actors: dict[str, set[str]] = {}
    yes, near, no = [], [], []           # near: the actor wrote, or it reads as delivery, but not both
    for p in pairs:
        r = items.get(p["item"])
        if r is None:
            continue
        names = actors.setdefault(p["actor"], party_names(conn, p["actor"]))
        by_actor = bool(names & senders.get(r["from_addr"], {r["from_addr"]}))
        delivered = bool(DELIVERY.search(r["body"][:2000]))
        row = (f"belief:{p['id']}|item:{r['id']}", fulfil_state(p, reading_text(r)), _group(r))
        (yes if by_actor and delivered else near if by_actor or delivered else no).append(row)
    k = min(n // 2, len(yes))            # true fulfilments are rare: the near misses are where the team finds more
    m = min(n // 4, len(near))
    return [(*row, "yes") for row in rng.sample(yes, k)] + [(*row, "no") for row in rng.sample(near, m)] + \
        [(*row, "no") for row in rng.sample(no, min(len(no), max(k, n // 4)))]


def _contradicts(conn: psycopg.Connection, n: int, rng: random.Random) -> list[Row]:
    cols = "b.id, b.kind, b.actor, b.other, b.statement, b.when_text, b.due_at, i.thread_key, i.id AS item"
    changed = conn.execute(
        f"SELECT {cols}, n.id AS nid, n.kind AS nkind, n.actor AS nactor, n.other AS nother, "
        "n.statement AS nstatement, n.when_text AS nwhen_text, n.due_at AS ndue_at FROM beliefs n "
        "JOIN beliefs b ON b.id = n.supersedes JOIN items i ON i.id = b.item_id "
        "WHERE b.trust <> 'quarantined' AND n.trust <> 'quarantined'").fetchall()
    yes, no = [], []
    for r in changed:
        new = {"kind": r["nkind"], "actor": r["nactor"], "other": r["nother"], "statement": r["nstatement"],
               "when_text": r["nwhen_text"]}
        moved = (r["due_at"] != r["ndue_at"]) or (r["when_text"].strip().lower() != r["nwhen_text"].strip().lower())
        (yes if moved else no).append((f"belief:{r['id']}|belief:{r['nid']}", contradict_state(r, new),
                                       _group({"thread_key": r["thread_key"], "id": r["item"]})))
    owner = party_names(conn, "owner")
    unrelated = conn.execute(
        f"SELECT {cols}, n.id AS nid, n.kind AS nkind, n.actor AS nactor, n.other AS nother, "
        "n.statement AS nstatement, n.when_text AS nwhen_text FROM beliefs b JOIN beliefs n ON n.id > b.id "
        "AND n.supersedes IS DISTINCT FROM b.id AND b.supersedes IS DISTINCT FROM n.id "
        "AND n.item_id <> b.item_id AND (n.actor IN (b.actor, b.other) OR n.other IN (b.actor, b.other)) "
        "JOIN items i ON i.id = b.item_id WHERE b.kind IN ('decision', 'commitment') "
        "AND b.trust <> 'quarantined' AND n.trust <> 'quarantined' "
        "AND n.kind IN ('decision', 'commitment') AND NOT (b.actor = ANY(%s) AND n.actor = ANY(%s)) "
        "ORDER BY md5(b.id::text || n.id::text) LIMIT %s", (sorted(owner), sorted(owner), n)).fetchall()
    for r in unrelated:
        new = {"kind": r["nkind"], "actor": r["nactor"], "other": r["nother"], "statement": r["nstatement"],
               "when_text": r["nwhen_text"]}
        no.append((f"belief:{r['id']}|belief:{r['nid']}", contradict_state(r, new),
                   _group({"thread_key": r["thread_key"], "id": r["item"]})))
    k = min(n // 2, len(yes))
    picked_no = rng.sample(no, min(len(no), max(k, n // 4)))     # positives are rare: keep some extra negatives
    return [(*row, "yes") for row in rng.sample(yes, k)] + [(*row, "no") for row in picked_no]


def _todo(conn: psycopg.Connection, n: int, rng: random.Random, mailbox: str) -> list[Row]:
    rows = conn.execute(
        "SELECT b.id, b.actor, b.other, b.statement, b.when_text, i.thread_key, i.id AS item FROM beliefs b "
        "JOIN items i ON i.id = b.item_id WHERE b.kind = 'commitment' AND b.trust <> 'quarantined' "
        "AND b.actor = ANY(%s)", (sorted(owner_names(conn, mailbox)),)).fetchall()
    return [(f"belief:{r['id']}", todo_state(r), _group({"thread_key": r["thread_key"], "id": r["item"]}), None)
            for r in rng.sample(rows, min(n, len(rows)))]


def record_assistant(conn: psycopg.Connection, name: str, verdicts: dict[str, str]) -> int:
    """The assistant's checks (yes / no / skip) on queued examples, kept as their own source. Returns how many."""
    n = 0
    for subject, value in verdicts.items():
        if value not in ("yes", "no", "skip") or not conn.execute(
                "SELECT 1 FROM label_examples WHERE question = %s AND subject = %s", (name, subject)).fetchone():
            continue
        conn.execute("INSERT INTO labels (question, subject, value, source) VALUES (%s, %s, %s, 'assistant') "
                     "ON CONFLICT (question, subject, source) DO UPDATE SET value = EXCLUDED.value", (name, subject,
                                                                                                    value))
        n += 1
    conn.commit()
    return n
