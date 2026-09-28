"""Load the fictional demo world (demo_data/) into the local services.

reset:  wipe the database, load entities / relations / decisions / promise history / calendar /
        persona, empty Mailpit and fill it with the inbox emails, copy the vault, files, voice notes
        and outside-world pages into var/, and freeze the demo clock at Thu 8 Oct 08:55.
play:   send every live email whose time has come on the demo clock (safe to run repeatedly).
"""
from __future__ import annotations

import shutil
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import yaml
from psycopg.types.json import Jsonb

from omnitrix.config import Settings
from omnitrix.core.clock import Clock, ClockStore
from omnitrix.core.db import Database
from omnitrix.core.ids import new_id

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "demo_data"
VAR = ROOT / "var"
SENT_KEY = "demo_live_sent"
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# documents that arrive as email attachments; the rest are dropped into the watched folder
ATTACHED_ONLY = {"greenpack_price_revision.pdf", "invoice_quickpay_INV-4471.pdf",
                 "kaveri_bank_renewal_checklist.pdf", "mehta_q4_costing.pdf"}


def load_yaml(name: str) -> dict:
    return yaml.safe_load((DATA / name).read_text())


def persona() -> dict:
    return load_yaml("persona.yaml")


def emails() -> list[dict]:
    return load_yaml("emails.yaml")["emails"]


# ------------------------------------------------------------------------------------------- calendar

def expand_calendar(spec: dict) -> list[dict]:
    """Single events plus recurring ones expanded into occurrences, sorted by start."""
    events = list(spec["events"])
    for rec in spec.get("recurring", []):
        day: date = rec["from"]
        skip = set(rec.get("except", []))
        while day <= rec["until"]:
            if WEEKDAYS[day.weekday()] in rec["weekdays"] and day not in skip:
                events.append({**{k: v for k, v in rec.items() if k not in ("weekdays", "from", "until", "except")},
                               "id": f"{rec['id']}_{day:%m%d}",
                               "start": f"{day}T{rec['start']}", "end": f"{day}T{rec['end']}"})
            day += timedelta(days=1)
    return sorted(events, key=lambda e: e["start"])


def _local(text: str, tz: ZoneInfo) -> datetime:
    dt = datetime.fromisoformat(str(text))
    return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt


# --------------------------------------------------------------------------------------------- world

async def load_world(db: Database, tz: ZoneInfo) -> dict[str, int]:
    """Insert the knowledge-graph seed, decisions, promise history, calendar and persona."""
    ents = load_yaml("entities.yaml")
    counts: dict[str, int] = {}
    async with db.connection() as conn, conn.transaction():
        n = 0
        for group, kind in (("people", "person"), ("organizations", "organization"), ("projects", "project")):
            for e in ents[group]:
                await conn.execute(
                    "INSERT INTO entities (id, type, name, aliases, importance, details) VALUES (%s,%s,%s,%s,%s,%s)",
                    (e["id"], kind, e["name"], e.get("aliases", []), e.get("importance", 1),
                     Jsonb(e.get("details", {}))))
                n += 1
        counts["entities"] = n

        for src, rel, dst in ents["relations"]:
            await conn.execute("INSERT INTO relations (id, from_entity, to_entity, type) VALUES (%s,%s,%s,%s)",
                               (new_id("relation"), src, dst, rel))
        counts["relations"] = len(ents["relations"])

        for d in load_yaml("decisions.yaml")["decisions"]:
            source_id = None
            if d.get("source"):
                source_id = new_id("source")
                await conn.execute(
                    "INSERT INTO sources (id, type, location, received_at) VALUES (%s, 'obsidian_note', %s, %s)",
                    (source_id, f"vault://{d['source']}", _local(d["decided_at"], tz)))
            await conn.execute(
                "INSERT INTO decisions (id, what, why, alternatives_rejected, decided_by, decided_at, revisit_at, "
                "source_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (d["id"], d["what"], d["why"], d.get("alternatives_rejected", []), d.get("decided_by"),
                 _local(d["decided_at"], tz), _local(d["revisit_at"], tz) if d.get("revisit_at") else None,
                 source_id))
        counts["decisions"] = len(load_yaml("decisions.yaml")["decisions"])

        history = load_yaml("promise_history.yaml")["promises"]
        for p in history:
            done_at = _local(p["done_at"], tz)
            await conn.execute(
                "INSERT INTO promises (id, promiser, promisee, what, due_at, status, history) "
                "VALUES (%s,%s,%s,%s,%s,'done',%s)",
                (new_id("promise"), p["promiser"], p["promisee"], p["what"], _local(p["due_at"], tz),
                 Jsonb([{"at": done_at.isoformat(), "status": "done", "by": "seed"}])))
        counts["promise_history"] = len(history)

        cal = load_yaml("calendar.yaml")
        events = expand_calendar(cal)
        for e in events:
            await conn.execute(
                "INSERT INTO calendar_events (id, title, starts_at, ends_at, kind, flexible, location, attendees, "
                "external_uid) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (e["id"], e["title"], _local(e["start"], tz), _local(e["end"], tz), e.get("kind", "meeting"),
                 e.get("flexible", True), e.get("location"), e.get("attendees", []), f"{e['id']}@omnitrix.example"))
        counts["calendar_events"] = len(events)

    await db.set_setting("persona", _jsonable(persona()))
    return counts


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj


# --------------------------------------------------------------------------------------------- email

def build_message(spec: dict, by_id: dict[str, dict]) -> EmailMessage:
    msg = EmailMessage()
    sender = spec["from"]
    msg["From"] = f'{sender["name"]} <{sender["email"]}>'
    msg["To"] = ", ".join(f'{t["name"]} <{t["email"]}>' for t in spec["to"])
    if spec.get("cc"):
        msg["Cc"] = ", ".join(f'{t["name"]} <{t["email"]}>' for t in spec["cc"])
    msg["Subject"] = spec["subject"]
    msg["Date"] = format_datetime(datetime.fromisoformat(spec["at"]))
    msg["Message-ID"] = message_id(spec)
    parent = spec.get("in_reply_to")
    if parent:
        chain = [message_id(by_id[parent])]
        while by_id[parent].get("in_reply_to"):
            parent = by_id[parent]["in_reply_to"]
            chain.insert(0, message_id(by_id[parent]))
        msg["In-Reply-To"] = chain[-1]
        msg["References"] = " ".join(chain)
    msg["X-Omnitrix-Demo-Id"] = spec["id"]
    msg.set_content(spec["body"])
    for name in spec.get("attachments", []):
        msg.add_attachment((DATA / "documents" / name).read_bytes(), maintype="application", subtype="pdf",
                           filename=name)
    return msg


def message_id(spec: dict) -> str:
    return f"<{spec['id'].lower()}.demo@{spec['from']['email'].split('@', 1)[1]}>"


def send_emails(specs: list[dict], settings: Settings) -> None:
    by_id = {e["id"]: e for e in emails()}
    host = urlparse(settings.mailpit_url).hostname or "localhost"
    with smtplib.SMTP(host, settings.mailpit_smtp_port, timeout=10) as smtp:
        for spec in specs:
            smtp.send_message(build_message(spec, by_id))


def clear_mailpit(settings: Settings) -> None:
    httpx.delete(f"{settings.mailpit_url}/api/v1/messages", timeout=10).raise_for_status()


# ------------------------------------------------------------------------------------------------ var/

def prepare_var() -> dict[str, int]:
    """Fresh working copies, so agents can write to the vault without touching the seed."""
    counts = {}
    for name, src, pattern in (("vault", DATA / "obsidian-vault", None),
                               ("outside-world", DATA / "outside-world", None),
                               ("voice", DATA / "voice-notes", "*.wav"),
                               ("files", DATA / "documents", "*.pdf")):
        dst = VAR / name
        if dst.exists():
            shutil.rmtree(dst)
        if pattern is None:
            shutil.copytree(src, dst)
        else:
            dst.mkdir(parents=True)
            for f in src.glob(pattern):
                if name == "files" and f.name in ATTACHED_ONLY:
                    continue
                shutil.copy2(f, dst / f.name)
        counts[name] = sum(1 for p in dst.rglob("*") if p.is_file() and p.name != ".gitkeep")
    return counts


# ------------------------------------------------------------------------------------------ commands

async def reset(db: Database, settings: Settings) -> dict[str, int]:
    await db.reset()
    await db.migrate()
    counts = await load_world(db, settings.tz)
    clock = Clock(settings.tz)
    clock.freeze(datetime.fromisoformat(persona()["demo"]["clock_start"]))
    await ClockStore(db).save(clock)
    await db.set_setting(SENT_KEY, [])
    clear_mailpit(settings)
    inbox = [e for e in emails() if e["stage"] == "inbox"]
    send_emails(inbox, settings)
    counts["inbox_emails"] = len(inbox)
    counts.update({f"var/{k}": v for k, v in prepare_var().items()})
    return counts


async def live_status(db: Database) -> tuple[list[dict], set[str]]:
    sent = set(await db.get_setting(SENT_KEY) or [])
    return [e for e in emails() if e["stage"] == "live"], sent


async def send_live(db: Database, settings: Settings, ids: list[str]) -> list[str]:
    live, sent = await live_status(db)
    by_id = {e["id"]: e for e in live}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise KeyError(f"not live emails: {', '.join(unknown)} (live: {', '.join(by_id)})")
    send_emails([by_id[i] for i in ids], settings)
    await db.set_setting(SENT_KEY, sorted(sent | set(ids)))
    return ids


async def play(db: Database, settings: Settings, clock: Clock) -> list[str]:
    """Send every live email that is due by the demo clock and has not been sent yet."""
    live, sent = await live_status(db)
    due = [e["id"] for e in live if e["id"] not in sent and datetime.fromisoformat(e["at"]) <= clock.now()]
    return await send_live(db, settings, due) if due else []
