"""Connectors turn user-owned data into RawDocs. Demo sources today (Mailpit, the Obsidian vault copy, a
watched folder); real sources later (IMAP, a real vault, Drive exports) only need a new connector."""
from __future__ import annotations

import hashlib
import io
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import yaml
from pypdf import PdfReader

from .text import normalize


@dataclass
class Attachment:
    filename: str
    content_type: str
    text: str


@dataclass
class RawDoc:
    kind: str                      # email | file | obsidian_note (sources.type)
    location: str                  # stable address of the item
    received_at: datetime
    title: str
    doc_type: str                  # email, meeting, person, project, note, pdf...
    text: str
    meta: dict = field(default_factory=dict)
    # email only
    message_id: str | None = None
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    from_addr: str | None = None
    from_name: str | None = None
    to: list[tuple[str, str]] = field(default_factory=list)     # (name, address)
    cc: list[tuple[str, str]] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    frontmatter: dict = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.title}\n{self.text}".encode()).hexdigest()


def pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return normalize("\n\n".join(page.extract_text() or "" for page in reader.pages))


# --------------------------------------------------------------------------------------------- email

class MailpitConnector:
    """Reads every message in the local Mailpit inbox (the demo stand-in for IMAP)."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def fetch(self) -> AsyncIterator[RawDoc]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as http:
            start, summaries = 0, []
            while True:
                page = (await http.get("/api/v1/messages", params={"start": start, "limit": 200})).json()
                summaries += page["messages"]
                start += len(page["messages"])
                if not page["messages"] or start >= page["total"]:
                    break
            for s in sorted(summaries, key=lambda m: m.get("Date") or m["Created"]):
                m = (await http.get(f"/api/v1/message/{s['ID']}")).json()
                headers = (await http.get(f"/api/v1/message/{s['ID']}/headers")).json()
                atts = []
                for a in m.get("Attachments", []):
                    data = (await http.get(f"/api/v1/message/{s['ID']}/part/{a['PartID']}")).content
                    text = pdf_text(data) if a["ContentType"] == "application/pdf" else ""
                    atts.append(Attachment(a["FileName"], a["ContentType"], text))
                refs = " ".join(headers.get("References", [])).split()
                yield RawDoc(
                    kind="email",
                    location=f"mailpit://<{m['MessageID']}>",
                    received_at=datetime.fromisoformat(m["Date"]),
                    title=m["Subject"],
                    doc_type="email",
                    text=normalize(m.get("Text") or ""),
                    meta={"demo_id": (headers.get("X-Omnitrix-Demo-Id") or [None])[0], "mailpit_id": m["ID"]},
                    message_id=f"<{m['MessageID']}>",
                    in_reply_to=(headers.get("In-Reply-To") or [None])[0],
                    references=refs,
                    from_addr=m["From"]["Address"],
                    from_name=m["From"]["Name"],
                    to=[(t["Name"], t["Address"]) for t in m.get("To") or []],
                    cc=[(t["Name"], t["Address"]) for t in m.get("Cc") or []],
                    attachments=atts,
                )


# ------------------------------------------------------------------------------------------- obsidian

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class VaultConnector:
    """Markdown notes from an Obsidian vault (frontmatter + body)."""

    def __init__(self, root: Path, tz: ZoneInfo):
        self.root = root
        self.tz = tz

    async def fetch(self) -> AsyncIterator[RawDoc]:
        for path in sorted(self.root.rglob("*.md")):
            raw = path.read_text()
            fm: dict = {}
            m = FRONTMATTER.match(raw)
            if m:
                fm = yaml.safe_load(m.group(1)) or {}
                raw = raw[m.end():]
            heading = re.search(r"^# (.+)$", raw, re.MULTILINE)
            title = heading.group(1).strip() if heading else path.stem
            when = self._when(fm, path)
            rel = path.relative_to(self.root).as_posix()
            yield RawDoc(kind="obsidian_note", location=f"vault://{rel}", received_at=when, title=title,
                         doc_type=str(fm.get("type", "note")), text=normalize(raw),
                         meta={"path": rel}, frontmatter=fm)

    def _when(self, fm: dict, path: Path) -> datetime:
        if fm.get("date"):
            return datetime.fromisoformat(f"{fm['date']}T{fm.get('time', '09:00')}").replace(tzinfo=self.tz)
        return datetime.fromtimestamp(path.stat().st_mtime, self.tz)


# ------------------------------------------------------------------------------------------- files

class FolderConnector:
    """PDFs (and plain text) dropped into a watched folder."""

    def __init__(self, root: Path, received_at: datetime):
        self.root = root
        self.received_at = received_at

    async def fetch(self) -> AsyncIterator[RawDoc]:
        for path in sorted(self.root.iterdir()):
            if path.suffix.lower() == ".pdf":
                text = pdf_text(path.read_bytes())
            elif path.suffix.lower() in (".txt", ".md"):
                text = normalize(path.read_text())
            else:
                continue
            first_lines = [ln for ln in text.splitlines() if ln.strip()][:2]
            title = first_lines[1] if len(first_lines) > 1 else path.stem
            yield RawDoc(kind="file", location=f"file://{path.name}", received_at=self.received_at, title=title,
                         doc_type=path.suffix.lower().lstrip("."), text=text, meta={"filename": path.name})
