"""Herald: the one way engram reaches the owner (docs/research/agent-roster-review.md §2; brain-design D46/D47).

Roles post cards; Herald routes them, the watch shows them, and the owner's tap goes back to the role that asked.

- Memory, promises: a commitment or meeting of the owner's coming due in the next hour, or overdue by less than a
  day. Buttons: done / snooze.
- Memory, checks: a fulfils or contradicts link the judge found and the owner has not settled (011_checks.sql).
  "Yes" confirms it, "no" rejects it. Either way the verdict is a human label for adapter v2, stored with the
  material the judge read (derive.owner_verdict), so it trains like a checked example. A confirmed fulfilment
  closes the commitment, and a rejected one the judge had already closed reopens it.
- Librarian, arrivals: a fresh incoming item (sent in the last two days) from which Memory took a meeting or a
  commitment.

Routing is code, not a model: rules now, learning later (the owner's choice). A card buzzes now if it is due or
touches a meeting soon, and everything else waits in the digest. Quiet hours and a buzz budget per hour move even
urgent cards to the digest, because warnings habituate within a workweek (notes E §9). Every tap goes into the
ledger with its latency, which is the data the small judge's notify question (D47) will be trained on."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg

from . import derive
from .judge import Answer, append

DUE_SOON = timedelta(hours=1)           # a promise buzzes this long before it is due
OVERDUE = timedelta(days=1)             # ...and keeps its card this long after
FRESH = timedelta(days=2)               # an arrival older than this is history, not news
MEETING_SOON = timedelta(days=2)        # a contradiction touching a meeting this close buzzes
BUDGET = 6                              # buzzes per hour; more go to the digest
QUIET = (time(22, 0), time(7, 0))       # owner's local time: nothing buzzes
SNOOZE = timedelta(hours=1)

DONE, SNOOZE_ACT = {"id": "done", "label": "Done"}, {"id": "snooze", "label": "In 1 h"}
YES, NO = {"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}
OK, LATER = {"id": "ok", "label": "OK"}, {"id": "later", "label": "Later"}


def local_timezone() -> str:
    """This Mac's time zone (the watch's wearer is next to it), e.g. 'Asia/Kolkata'; UTC if it cannot be read."""
    target = str(Path("/etc/localtime").resolve())
    return target.split("zoneinfo/", 1)[1] if "zoneinfo/" in target else "UTC"


def sweep(conn: psycopg.Connection, now: datetime, tz: str, owner: set[str]) -> list[dict]:
    """Post a card for everything that should reach the owner and has none yet (`tz`: the wearer's time zone, for
    quiet hours). Returns the new cards."""
    posted = []
    for card in [*_due(conn, now, owner), *_checks(conn, now), *_arrivals(conn, now)]:
        card["route"], card["why"] = route(conn, card, now, tz)
        row = conn.execute(
            "INSERT INTO herald_cards (role, kind, subject, title, body, actions, route, why, created_at, show_after) "
            "VALUES (%(role)s, %(kind)s, %(subject)s, %(title)s, %(body)s, %(actions)s, %(route)s, %(why)s, %(now)s, "
            "%(now)s) ON CONFLICT (subject) DO NOTHING RETURNING id",     # the sweep's clock, not the database's
            {**card, "actions": json.dumps(card["actions"]), "now": now}).fetchone()
        if row:
            posted.append({**card, "id": row["id"]})
    conn.commit()
    return posted


def route(conn: psycopg.Connection, card: dict, now: datetime, tz: str) -> tuple[str, str]:
    """('now' | 'digest', why): the code rules (D46/D47 before there is data to learn from)."""
    urgent = card.pop("urgent", "")
    if not urgent:
        return "digest", "not urgent: in the digest"
    local = now.astimezone(ZoneInfo(tz)).time()
    if local >= QUIET[0] or local < QUIET[1]:
        return "digest", f"{urgent}, but quiet hours"
    buzzed = conn.execute("SELECT count(*) AS n FROM herald_cards WHERE route = 'now' AND created_at > %s",
                          (now - timedelta(hours=1),)).fetchone()["n"]
    if buzzed >= BUDGET:
        return "digest", f"{urgent}, but {BUDGET} buzzes in the last hour already"
    return "now", urgent


def cards(conn: psycopg.Connection, now: datetime, deliver: bool = False) -> list[dict]:
    """Open cards to show: buzz-worthy first, then the digest (newest first). `deliver`: a watch is receiving
    them, so the first delivery time is kept (the tap's latency is measured from it)."""
    rows = conn.execute(
        "SELECT id, role, kind, title, body, actions, route, why, created_at FROM herald_cards "
        "WHERE decided_at IS NULL AND route <> 'drop' AND show_after <= %s "
        "ORDER BY route = 'now' DESC, created_at DESC LIMIT 40", (now,)).fetchall()
    if deliver and rows:
        conn.execute("UPDATE herald_cards SET delivered_at = %s WHERE id = ANY(%s) AND delivered_at IS NULL",
                     (now, [r["id"] for r in rows]))
        conn.commit()
    return [{**r, "created_at": r["created_at"].isoformat(timespec="seconds")} for r in rows]


def decide(conn: psycopg.Connection, card_id: int, action: str, by: str, now: datetime) -> dict:
    """The owner's tap: goes back to the role that posted the card, into the ledger, and settles the card (a
    snooze only moves it)."""
    c = conn.execute("SELECT * FROM herald_cards WHERE id = %s FOR UPDATE", (card_id,)).fetchone()
    if c is None or c["decided_at"] is not None:
        conn.rollback()
        raise LookupError("no such open card")
    if action not in {a["id"] for a in c["actions"]}:
        conn.rollback()
        raise ValueError(f"{action!r} is not an answer to this card")
    if action in ("snooze", "later"):
        conn.execute("UPDATE herald_cards SET show_after = %s WHERE id = %s", (now + SNOOZE, card_id))
        conn.commit()
        return {"ok": True, "snoozed_until": (now + SNOOZE).isoformat(timespec="minutes")}
    _apply(conn, c, action)
    conn.execute("UPDATE herald_cards SET decided_at = %s, decision = %s, decided_by = %s WHERE id = %s",
                 (now, action, by, card_id))
    conn.commit()
    ms = (now - (c["delivered_at"] or c["created_at"])).total_seconds() * 1000
    append(conn, f"herald:{c['kind']}", c["subject"], hashlib.sha256(c["body"].encode()).hexdigest(),
           Answer("H", f"owner:{by}", {}, {action: 1.0}, action, True, max(ms, 0.0)))
    return {"ok": True}


# ------------------------------------------------------------------------------------------------ the roles

def _due(conn: psycopg.Connection, now: datetime, owner: set[str]) -> list[dict]:
    rows = conn.execute(
        "SELECT id, kind, statement, due_at FROM current_beliefs WHERE kind IN ('commitment', 'meeting') "
        "AND status = 'open' AND trust <> 'quarantined' AND due_at BETWEEN %(from)s AND %(to)s "
        "AND (trust = 'owner' OR actor = ANY(%(owner)s) OR other = ANY(%(owner)s))",
        {"from": now - OVERDUE, "to": now + DUE_SOON, "owner": list(owner)}).fetchall()
    out = []
    for b in rows:
        minutes = round((b["due_at"] - now).total_seconds() / 60)
        when = f"in {minutes} min" if minutes > 0 else "now" if minutes == 0 else f"{_ago(-minutes)} overdue"
        meeting = b["kind"] == "meeting"
        out.append({"role": "memory", "kind": "due", "subject": f"belief:{b['id']}:due",
                    "title": f"Meeting {when}" if meeting else f"Due {when}", "body": b["statement"],
                    "actions": [OK if meeting else DONE, SNOOZE_ACT],
                    "urgent": "a meeting is coming up" if meeting else "a promise is due"})
    return out


def _checks(conn: psycopg.Connection, now: datetime) -> list[dict]:
    rows = conn.execute(
        "SELECT l.id, l.kind, l.p, l.settled, b.statement AS old, b.kind AS old_kind, b.due_at, "
        "n.statement AS new, i.subject, i.sent_at FROM belief_links l JOIN beliefs b ON b.id = l.belief_id "
        "JOIN items i ON i.id = l.item_id LEFT JOIN beliefs n ON n.id = l.new_belief "
        "WHERE l.verdict = 'pending'").fetchall()
    out = []
    for r in rows:
        if r["kind"] == "fulfils":
            closed = " (the judge closed it)" if r["settled"] else ""
            out.append({"role": "memory", "kind": "fulfils", "subject": f"link:{r['id']}", "title": f"Done?{closed}",
                        "body": f"“{r['old']}”, done by “{r['subject'] or '(no subject)'}” "
                                f"({_day(r['sent_at'])})?", "actions": [YES, NO], "urgent": ""})
        else:
            soon = r["old_kind"] == "meeting" and r["due_at"] is not None and \
                timedelta(0) <= r["due_at"] - now < MEETING_SOON
            out.append({"role": "memory", "kind": "contradicts", "subject": f"link:{r['id']}", "title": "Changed?",
                        "body": f"Was: “{r['old']}”\nNow: “{r['new'] or r['subject']}”", "actions": [YES, NO],
                        "urgent": "a meeting you have may have moved" if soon else ""})
    return out


def _arrivals(conn: psycopg.Connection, now: datetime) -> list[dict]:
    rows = conn.execute(
        "SELECT i.id, i.from_addr, i.subject, s.kinds, p.name, "
        "(SELECT b.statement FROM current_beliefs b WHERE b.item_id = i.id AND b.trust <> 'quarantined' "
        " ORDER BY b.kind = 'meeting' DESC, b.id LIMIT 1) AS statement "
        "FROM items i JOIN memory_scans s ON s.item_id = i.id "
        "LEFT JOIN people p ON i.from_addr = ANY(p.addresses) "
        "WHERE i.direction = 'in' AND i.sent_at >= %s AND s.kinds && ARRAY['meeting', 'commitment']",
        (now - FRESH,)).fetchall()
    return [{"role": "librarian", "kind": "arrival", "subject": f"item:{r['id']}",
             "title": f"New from {r['name'] or r['from_addr'].split('@')[0]}",
             "body": r["statement"] or r["subject"] or "", "actions": [OK, LATER],
             "urgent": "a new meeting request" if "meeting" in r["kinds"] else "a new request for you"}
            for r in rows if r["statement"]]


def _apply(conn: psycopg.Connection, c: dict[str, Any], action: str) -> None:
    """Hand the owner's answer back to the role that asked."""
    if c["kind"] == "due" and action == "done":
        conn.execute("UPDATE beliefs SET status = 'done' WHERE id = %s AND status = 'open'",
                     (int(c["subject"].split(":")[1]),))
    elif c["kind"] in ("fulfils", "contradicts"):
        link = conn.execute("SELECT * FROM belief_links WHERE id = %s", (int(c["subject"].split(":")[1]),)).fetchone()
        conn.execute("UPDATE belief_links SET verdict = %s WHERE id = %s",
                     ("confirmed" if action == "yes" else "rejected", link["id"]))
        if link["kind"] == "fulfils":
            status = ("done", "open") if action == "yes" else ("open", "done")      # (to, from)
            conn.execute("UPDATE beliefs SET status = %s WHERE id = %s AND status = %s",
                         (status[0], link["belief_id"], status[1]))
            derive.owner_verdict(conn, "fulfilled", link["belief_id"], action, item=link["item_id"])
        else:
            derive.owner_verdict(conn, "contradicts", link["belief_id"], action, new_belief=link["new_belief"])

def _ago(minutes: int) -> str:
    return f"{minutes} min" if minutes < 90 else f"{round(minutes / 60)} h"


def _day(d: datetime | None) -> str:
    return f"{d:%d %b %Y}" if d else "undated"
