"""Knowledge -> memory: distil commitments, decisions and meetings from items into bitemporal beliefs (LR §1, §3.6).

Per item: (1) System 1 gates — one-token questions — decide which kinds the item holds; most items stop here
(LR §4.1: gate before extracting). (2) One System 2 call extracts the kinds found, constrained to a JSON schema.
(3) Code keeps an extracted belief only if its quote occurs verbatim in the item (a free guard against invented
facts) and resolves its time words against the item's date (LR §3.4: do time in code). (4) A belief that restates
a current one about the same parties supersedes it: the old one's `recorded` range is closed, nothing is deleted.
An older item read later (a backfill) is kept as history and never replaces newer news. (5) Memory's two checks
(D26, D27): a later message in a commitment's thread may carry it out (`fulfilled`; settled yes closes it), and a new
belief may contradict a current decision or commitment of the same people (`contradicts`; always the owner's to
see, never acted on). Supersession matches parties by their lower-cased names; the contradiction check widens them
through `people` aliases ("Vince" and "Vince Kaminski" are one person there)."""
from __future__ import annotations

import re
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import dateparser
import psycopg

from .judge import Judge, Question, noul

KINDS = ("commitment", "decision", "meeting")
REMEMBER = noul("remember", "Does this message hold something its owner should remember: a specific commitment or "
                            "task (someone promises, agrees or is asked to do something), a decision that was made, "
                            "or a meeting, call or visit being set up or changed, involving the owner or the people "
                            "they work with? Answer no for newsletters, marketing, automated system notices, general "
                            "announcements, thank-you notes, jokes, and messages with nothing specific to act on or "
                            "recall.")
SAME = noul("same_belief", "Do the existing and the new entry describe the same commitment, decision or meeting "
                           "(possibly with changed details)?")
FULFILLED = noul("fulfilled", "Does the later message show that the commitment has been carried out: the thing was "
                              "done, sent, delivered, booked or attended? Answer no if it only repeats or confirms "
                              "the promise, asks about it, reports partial progress, or is about something else.")
CONTRADICTS = noul("contradicts", "Can the existing and the new entry not both hold: does the new one go against what "
                                  "was decided or promised in the existing one? Answer no if the new entry restates "
                                  "it, adds detail, or is about something else.")
MEETING = noul("meeting_request", "Does this message propose, request, confirm or change a meeting, call or visit "
                                  "for the owner or the people they work with, at a stated time or asking to find "
                                  "one? Answer no for past meetings, general invitations to events, and newsletters.")
EXTRACT_SYSTEM = ("You extract facts for a person's memory from one item: an email, or part of a meeting transcript. "
                  "Include only what the item itself states. Copy `quote` verbatim from the item. `when` is the exact "
                  "words the item uses for the deadline or time, or an empty string.")
FIELDS = ("kind", "actor", "other", "statement", "when", "quote")
MEMORY_LOCK = 0x656E6D65          # advisory lock: one memory build per brain at a time ('enme')
ITEM_LOCK = 0x656E6D69            # with an item id: one build on an item at a time ('enmi')
SCHEMA = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
    "type": "object", "required": ["kind", "actor", "other", "statement", "when", "quote"],
    "properties": {"kind": {"type": "string", "enum": list(KINDS)}, "actor": {"type": "string"},
                   "other": {"type": "string"}, "statement": {"type": "string"}, "when": {"type": "string"},
                   "quote": {"type": "string"}}}}}}
READ_CHARS = 4000


class Extractor(Protocol):
    def generate_json(self, model: str, system: str, user: str, schema: dict, max_tokens: int = 600) -> dict: ...


BULK_TEXT = re.compile(r"unsubscribe|newsletter|to be removed|click here|opt.?out|this message was sent|mailing list|"
                       r"return-path:|content-transfer-encoding", re.I)
BULK_SENDER = re.compile(r"noreply|no-reply|newsletter|webmaster|arsystem|insideralerts|@bdcimail|perfmgmt|"
                         r"no\.address|announce|mailer|daemon", re.I)
INJECTION = re.compile(r"ignore (all |any )?(previous|prior|above) (instructions|messages)|disregard (the|your) "
                       r"(instructions|rules)|you are now|system prompt|as an ai (model|assistant)|<\|im_start\|>|"
                       r"\bassistant:|developer mode|jailbreak|call the tool|execute the following", re.I)
PASS = 0.2           # S1 P(remember) below this is not extracted: keeps 93-95% of memorable items (LR §10.7)
SURE = 0.5           # between PASS and SURE the gate is unsure: extracted, and queued for the owner's verdict


def bulk(r: dict[str, Any]) -> bool:
    """S0: newsletters, marketing and machine mail, by text and sender. On the hand-labelled set it dropped ~20% of
    items and no memorable one."""
    return bool(BULK_TEXT.search(r["body"][:4000]) or BULK_SENDER.search(r["from_addr"]))


@dataclass
class MemoryStats:
    scanned: int = 0
    bulk: int = 0                        # dropped by S0
    passed: int = 0                      # sent to extraction by the S1 gate
    unsure: list[dict[str, Any]] = field(default_factory=list)    # passed, but worth the owner's verdict
    extraction_calls: int = 0
    beliefs: int = 0
    superseded: int = 0
    unquoted: int = 0                    # dropped: the quote is not in the item
    malformed: int = 0                   # extraction output that was not valid JSON / missing fields: skipped
    fulfilled: int = 0                   # open commitments a later message carried out (settled: closed)
    contradictions: int = 0              # new beliefs that go against a current decision or commitment


def quote_in(quote: str, text: str) -> bool:
    """Does the quote occur in the text, ignoring case, whitespace and trailing punctuation?"""
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()  # noqa: E731
    q = norm(quote).rstrip(".!?,;:")
    return len(q) >= 8 and q in norm(text)


def resolve_when(when: str, sent_at: datetime | None, timezone: str) -> datetime | None:
    """The moment `when` refers to, read relative to the item's date in the owner's timezone; None if unclear."""
    if not when.strip() or sent_at is None:
        return None
    local = sent_at.astimezone(ZoneInfo(timezone)).replace(tzinfo=None)    # "tomorrow" is the owner's tomorrow
    return dateparser.parse(when, settings={
        "RELATIVE_BASE": local, "PREFER_DATES_FROM": "future", "TIMEZONE": timezone, "TO_TIMEZONE": "UTC",
        "RETURN_AS_TIMEZONE_AWARE": True})


def reading_text(r: dict[str, Any]) -> str:
    """What an item says, with its quoted history only when the item itself says little (as in store.py)."""
    text = r["body"] if len(r["body"]) >= 200 or not r["quoted"] else f"{r['body']}\n\n{r['quoted']}"
    return f"Subject: {r['subject']}\nFrom: {r['from_addr']}\n\n{text}"[:READ_CHARS]


def build(conn: psycopg.Connection, judge: Judge, extractor: Extractor, model: str, owner: str, timezone: str,
          since: datetime | None = None, until: datetime | None = None, limit: int | None = None,
          on_item: Callable[[MemoryStats], None] | None = None, ids: list[int] | None = None,
          owner_says: Collection[int] = ()) -> MemoryStats:
    """Scan items not yet scanned (oldest first) and record the beliefs they hold. Resumable per item; one scan
    build per brain at a time, but a build of given `ids` (a note just added) runs beside it: each item is locked
    on its own. `owner_says`: items the owner explicitly asked to remember ("remember …" on the watch). They skip
    the gate, their beliefs are the owner's (trust 'owner'), and the owner's word becomes a human label."""
    if ids is None and not conn.execute("SELECT pg_try_advisory_lock(%s) AS ok", (MEMORY_LOCK,)).fetchone()["ok"]:
        raise RuntimeError("another memory build is running on this brain")
    try:
        return _build(conn, judge, extractor, model, owner, timezone, since, until, limit, on_item, ids,
                      set(owner_says))
    finally:
        if ids is None:
            conn.execute("SELECT pg_advisory_unlock(%s)", (MEMORY_LOCK,))
        conn.commit()


def _build(conn: psycopg.Connection, judge: Judge, extractor: Extractor, model: str, owner: str, timezone: str,
           since: datetime | None, until: datetime | None, limit: int | None,
           on_item: Callable[[MemoryStats], None] | None, ids: list[int] | None = None,
           owner_says: set[int] = frozenset()) -> MemoryStats:
    stats = MemoryStats()
    rows = conn.execute(
        "SELECT i.id, i.kind, i.sent_at, i.from_addr, i.to_addrs, i.subject, i.body, i.quoted, i.direction "
        "FROM items i "
        "WHERE NOT EXISTS (SELECT 1 FROM memory_scans s WHERE s.item_id = i.id) AND length(i.body) > 20 "
        "AND (%(since)s::timestamptz IS NULL OR i.sent_at >= %(since)s) "
        "AND (%(until)s::timestamptz IS NULL OR i.sent_at < %(until)s) "
        "AND (%(ids)s::bigint[] IS NULL OR i.id = ANY(%(ids)s)) ORDER BY i.sent_at LIMIT %(limit)s",
        {"since": since, "until": until, "limit": limit, "ids": ids}).fetchall()
    for r in rows:
        if not conn.execute("SELECT pg_try_advisory_lock(%s, %s) AS ok", (ITEM_LOCK, r["id"])).fetchone()["ok"] or \
                conn.execute("SELECT 1 FROM memory_scans WHERE item_id = %s", (r["id"],)).fetchone():
            conn.execute("SELECT pg_advisory_unlock(%s, %s)", (ITEM_LOCK, r["id"]))   # (no-op if not held)
            continue                                # another build has it, or finished it after our query
        try:
            _scan(conn, judge, extractor, model, owner, timezone, r, r["id"] in owner_says, stats)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s, %s)", (ITEM_LOCK, r["id"]))
        if on_item:
            on_item(stats)
    return stats


def _scan(conn: psycopg.Connection, judge: Judge, extractor: Extractor, model: str, owner: str, timezone: str,
          r: dict[str, Any], owner_says: bool, stats: MemoryStats) -> None:
    """One item: gate, extract, remember, check; then mark it scanned."""
    text, found = reading_text(r), []
    if owner_says:
        r = {**r, "owner_says": True}
        conn.execute("INSERT INTO labels (question, subject, value, source) VALUES ('remember', %s, 'yes', 'human') "
                     "ON CONFLICT (question, subject, source) DO UPDATE SET value = 'yes'", (f"item:{r['id']}",))
    is_bulk = not owner_says and bulk(r)
    p = 1.0 if owner_says else 0.0 if is_bulk else _p_remember(judge, text, r["id"])
    stats.bulk += is_bulk
    if not is_bulk:
        stats.fulfilled += _check_fulfilled(conn, judge, r, text)
    if p >= PASS:
        stats.passed += 1
        stats.extraction_calls += 1
        if p < SURE:
            stats.unsure.append({**r, "p": p})
        for x in _extract(extractor, model, _extract_prompt(r, text, list(KINDS), owner), stats):
            if not quote_in(x["quote"], text):
                stats.unquoted += 1
                continue
            superseded, belief = _remember(conn, judge, r, x, p, timezone)
            stats.superseded += superseded
            stats.contradictions += _check_contradicts(conn, judge, r, x, belief)
            stats.beliefs += 1
            found.append(x["kind"])
    conn.execute("INSERT INTO memory_scans (item_id, kinds) VALUES (%s, %s)", (r["id"], sorted(set(found))))
    conn.commit()
    stats.scanned += 1


def _p_remember(judge: Judge, text: str, item_id: int) -> float:
    """S1's P(worth remembering), from the small judge alone: the gate is recall-first, and precision comes from
    extraction (which may find nothing) and the owner's review."""
    tier, scorer = ("S1", judge.s1) if judge.s1 else ("S2", judge.s2)
    a = judge.answer(tier, scorer, REMEMBER, text, f"item:{item_id}")
    return a.probs.get("yes", 0.0) if a.logprobs else 1.0         # no valid answer: extract rather than lose it


def _extract(extractor: Extractor, model: str, prompt: str, stats: MemoryStats) -> list[dict[str, str]]:
    """The extracted entries that have every field as a string. Output that is not JSON (e.g. cut off at the token
    limit) is counted and skipped, so one bad item never blocks the items after it."""
    try:
        out = extractor.generate_json(model, EXTRACT_SYSTEM, prompt, SCHEMA, max_tokens=1500)
    except ValueError:
        stats.malformed += 1
        return []
    entries = (out.get("items") or []) if isinstance(out, dict) else []
    good = [x for x in entries if isinstance(x, dict) and all(isinstance(x.get(f), str) for f in FIELDS)]
    stats.malformed += len(entries) - len(good) if isinstance(entries, list) else 1
    return good


def _extract_prompt(r: dict[str, Any], text: str, kinds: list[str], owner: str) -> str:
    when = f"{r['sent_at']:%A %Y-%m-%d %H:%M}" if r["sent_at"] else "undated"
    what = (f"Meeting transcript ({when}), speakers: {', '.join(r['to_addrs'][:8])}" if r["kind"] == "meeting" else
            f"Email sent {when} to {', '.join(r['to_addrs'][:5])}")
    return (f"Owner: {owner}\n{what}\n{text}\n\nExtract every {' / '.join(kinds)} in this item; if there is none, "
            "return an empty list. For each give: kind; actor (who commits, decided, or sets it up); other (to whom "
            "/ with whom); statement (one line, third person); when; quote.")


def trust(r: dict[str, Any], x: dict[str, str]) -> str:
    """Where a belief's words came from (after OpenJarvis's fail-closed recall): the owner's own mail, someone
    else's, or text that reads like instructions to a model — quarantined, and never served as evidence."""
    if INJECTION.search(f"{x.get('statement', '')}\n{x.get('quote', '')}"):
        return "quarantined"
    if r.get("owner_says"):                     # the owner's own note, explicitly to be remembered
        return "owner"
    return "engram" if r.get("direction") == "out" else "external"


def _remember(conn: psycopg.Connection, judge: Judge, r: dict[str, Any], x: dict[str, str], confidence: float,
              timezone: str) -> tuple[int, int]:
    """Insert one belief; supersede a current belief about the same parties that the judge says it restates.
    Returns (1 if something was superseded else 0, the new belief's id)."""
    actor, other = x["actor"].strip().lower(), x["other"].strip().lower()
    due = resolve_when(x["when"], r["sent_at"], timezone)
    superseded, previous, newer = 0, None, None
    for old in conn.execute("SELECT id, statement, when_text, lower(valid) AS since FROM beliefs "
                            "WHERE upper_inf(recorded) AND kind = %s AND actor = %s AND other = %s "
                            "ORDER BY lower(valid) DESC NULLS LAST, id DESC LIMIT 5", (x["kind"], actor, other)):
        pair = f"Existing: {old['statement']} (when: {old['when_text'] or '-'})\n" \
               f"New: {x['statement']} (when: {x['when'] or '-'})"
        if judge.ask(SAME, pair, f"belief:{old['id']}|item:{r['id']}").value == "yes":
            if r["sent_at"] and old["since"] and r["sent_at"] < old["since"]:
                newer = old["since"]            # older news (e.g. a backfill): history, never the current belief
            else:
                conn.execute("UPDATE beliefs SET recorded = tstzrange(lower(recorded), now()) WHERE id = %s",
                             (old["id"],))
                previous, superseded = old["id"], 1
            break
    belief = conn.execute(
        "INSERT INTO beliefs (kind, actor, other, statement, due_at, when_text, valid, recorded, item_id, quote, "
        "confidence, supersedes, trust) VALUES (%s, %s, %s, %s, %s, %s, tstzrange(%s, %s), "
        "CASE WHEN %s THEN tstzrange(now(), now(), '[]') ELSE tstzrange(now(), NULL) END, %s, %s, %s, %s, %s) "
        "RETURNING id",
        (x["kind"], actor, other, x["statement"].strip(), due, x["when"].strip(), r["sent_at"], newer,
         newer is not None, r["id"], x["quote"].strip(), round(confidence, 4), previous, trust(r, x))).fetchone()
    return superseded, belief["id"]


CHECKS = 5           # candidates per check: the most recent open commitments / current beliefs


def _check_fulfilled(conn: psycopg.Connection, judge: Judge, r: dict[str, Any], text: str) -> int:
    """D27: does this item carry out an open commitment made earlier in its thread? A settled yes closes the
    commitment; an unsure yes is linked for the owner. Returns how many commitments it fulfils."""
    found = 0
    for b in conn.execute(
            "SELECT b.id, b.actor, b.other, b.statement, b.when_text FROM current_beliefs b "
            "JOIN items s ON s.id = b.item_id, items i "
            "WHERE i.id = %(item)s AND b.kind = 'commitment' AND b.status = 'open' AND b.trust <> 'quarantined' "
            "AND s.thread_key <> '' AND s.thread_key = i.thread_key AND b.item_id <> i.id "
            "AND COALESCE(s.sent_at < i.sent_at, s.id < i.id) "
            "ORDER BY s.sent_at DESC NULLS LAST, s.id DESC LIMIT %(k)s", {"item": r["id"], "k": CHECKS}).fetchall():
        value, p, settled = _small(judge, FULFILLED, fulfil_state(b, text), f"belief:{b['id']}|item:{r['id']}")
        if value != "yes":
            continue
        found += 1
        _link(conn, "fulfils", b["id"], r["id"], None, p, settled)
        if settled:
            conn.execute("UPDATE beliefs SET status = 'done' WHERE id = %s AND status = 'open'", (b["id"],))
    return found


def _check_contradicts(conn: psycopg.Connection, judge: Judge, r: dict[str, Any], x: dict[str, str],
                       belief: int) -> int:
    """D26: does the new belief go against a current decision or commitment of the same people? Recorded for the
    owner (Herald shows it; Guardian can show it on an approval), never acted on. Returns how many it contradicts."""
    owner = party_names(conn, "owner")
    names = party_names(conn, x["actor"]) | party_names(conn, x["other"])
    if names - owner:                   # nearly every belief involves the owner: match on the other party
        names -= owner
    if not names:
        return 0
    found = 0
    for b in conn.execute(
            "SELECT b.id, b.kind, b.actor, b.other, b.statement, b.when_text FROM current_beliefs b "
            "WHERE b.kind IN ('decision', 'commitment') AND b.id <> %(new)s AND b.item_id <> %(item)s "
            "AND b.trust <> 'quarantined' AND (b.actor = ANY(%(names)s) OR b.other = ANY(%(names)s)) "
            "AND (%(at)s::timestamptz IS NULL OR b.sent_at <= %(at)s) ORDER BY b.sent_at DESC NULLS LAST, b.id DESC "
            "LIMIT %(k)s",
            {"new": belief, "item": r["id"], "names": sorted(names), "at": r["sent_at"], "k": CHECKS}).fetchall():
        new = {**x, "when_text": x["when"]}
        value, p, _ = _small(judge, CONTRADICTS, contradict_state(b, new), f"belief:{b['id']}|belief:{belief}")
        if value == "yes":
            found += 1
            _link(conn, "contradicts", b["id"], r["id"], belief, p, False)     # always the owner's to confirm
    return found


def _small(judge: Judge, q: Question, state: str, subject: str) -> tuple[str, float, bool]:
    """The small judge's answer alone (value, P(value), settled): during a memory build an unsure answer goes to the
    owner, not the 14B, which is measured no better on what S1 is unsure of (LR §10.5)."""
    tier, scorer = ("S1", judge.s1) if judge.s1 else ("S2", judge.s2)
    a = judge.answer(tier, scorer, q, state, subject)
    return a.value, a.probs.get(a.value, 0.0), a.settled


def fulfil_state(b: dict[str, Any], text: str) -> str:
    """What `fulfilled` reads: the commitment, then the later message (as the memory gate reads it)."""
    return (f"Commitment: {b['actor']} to {b['other'] or '-'}: {b['statement']} (when: {b['when_text'] or '-'})"
            f"\n\nLater message:\n{text}")


def contradict_state(old: dict[str, Any], new: dict[str, Any]) -> str:
    """What `contradicts` reads: two beliefs, each with its kind, parties, statement and time words."""
    line = lambda b: (f"{b['kind']}: {b['actor']} / {b['other'] or '-'}: {b['statement']} "  # noqa: E731
                      f"(when: {b['when_text'] or '-'})")
    return f"Existing {line(old)}\nNew {line(new)}"


def _link(conn: psycopg.Connection, kind: str, belief: int, item: int, new_belief: int | None, p: float,
          settled: bool) -> None:
    conn.execute("INSERT INTO belief_links (kind, belief_id, item_id, new_belief, p, settled) "
                 "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (kind, belief_id, item_id) DO NOTHING",
                 (kind, belief, item, new_belief, round(p, 4), settled))


def party_names(conn: psycopg.Connection, name: str) -> set[str]:
    """The lower-cased names beliefs may use for this party: the name itself, plus the key and aliases of the one
    person it is known under (people.py)."""
    n = name.strip().lower()
    if not n:
        return set()
    rows = conn.execute("SELECT key, aliases FROM people WHERE key = %(n)s OR %(n)s = ANY(aliases) LIMIT 2",
                        {"n": n}).fetchall()
    if len(rows) != 1:                                    # unknown, or ambiguous: only the name itself
        return {n}
    return {n, rows[0]["key"], *rows[0]["aliases"]}
