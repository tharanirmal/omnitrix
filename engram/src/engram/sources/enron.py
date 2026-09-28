"""The Enron corpus (Hugging Face `corbt/enron-emails`: parquet rows with the original maildir path) read as one
person's mailbox. The folder each copy sat in and the owner's sent mail are kept: they are the owner's own
labels for what mattered and what they acted on (LR §9)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.dataset as ds

SENT_FOLDERS = frozenset({"sent", "sent_items", "_sent_mail", "_sent"})
# Folders every mailbox has; any other folder is one the owner made and filed into by hand.
SYSTEM_FOLDERS = SENT_FOLDERS | {"all_documents", "discussion_threads", "notes_inbox", "inbox", "deleted_items",
                                 "contacts", "calendar", "tasks", "archiving", "straw"}


@dataclass(frozen=True, slots=True)
class Message:
    ref: str                        # original location, e.g. 'kaminski-v/inbox/12.'
    folder: str                     # e.g. 'inbox', 'sent_items', 'projects/weather'
    sent_at: datetime | None
    from_addr: str
    to_addrs: tuple[str, ...]
    cc_addrs: tuple[str, ...]
    subject: str
    body: str


def read_mailbox(path: Path, owner: str) -> list[Message]:
    """Every file in `owner`'s mailbox (all folders, duplicates included)."""
    table = ds.dataset(path, format="parquet").to_table(
        columns=["file_name", "date", "from", "to", "cc", "subject", "body"],
        filter=pc.starts_with(pc.field("file_name"), f"{owner}/"),
    )
    return [
        Message(
            ref=r["file_name"],
            folder="/".join(r["file_name"].split("/")[1:-1]),
            sent_at=r["date"],
            from_addr=_addr(r["from"]),
            to_addrs=_addrs(r["to"]),
            cc_addrs=_addrs(r["cc"]),
            subject=(r["subject"] or "").strip(),
            body=r["body"] or "",
        )
        for r in table.to_pylist()
    ]


def owner_addresses(messages: Iterable[Message], min_sent: int = 20) -> set[str]:
    """The owner's own addresses, aliases included: whoever sent at least `min_sent` of the owner's sent mail."""
    counts = Counter(m.from_addr for m in messages if m.folder.split("/")[0] in SENT_FOLDERS)
    return {a for a, n in counts.items() if a and n >= min_sent}


def _addr(a: str | None) -> str:
    return (a or "").strip().lower()


def _addrs(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys(a for a in map(_addr, values or ()) if a))
