"""QMSum (Zhong et al., 2021; Hugging Face `pszemraj/qmsum-cleaned`): meeting transcripts with query-focused
summaries. Its AMI part is the business example: product teams (project manager, marketing, user interface,
industrial designer) designing a remote control across a series of meetings, full of decisions and action items.
Each meeting becomes a run of segments short enough for the memory judges to read whole, threaded under one
subject. QMSum carries no dates, so meeting items are undated."""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq

from .enron import Message

AMI_ROLES = frozenset({"Project Manager", "Marketing", "User Interface", "Industrial Designer"})
SEGMENT_CHARS = 3500                # memory reads 4000 characters of an item, headers included
TURN = re.compile(r"^([^:\n]{2,40}): (.*)$")


@dataclass(frozen=True)
class Meeting:
    id: str                                     # from the transcript's hash
    turns: tuple[tuple[str, str], ...]          # (speaker, words)
    queries: tuple[tuple[str, str], ...]        # (query, reference summary; empty in the test split)

    @property
    def is_ami(self) -> bool:
        return {s for s, _ in Counter(s for s, _ in self.turns).most_common(4)} <= AMI_ROLES


def read_meetings(path: Path) -> list[Meeting]:
    """Every distinct meeting in the parquet splits, with all the queries asked about it."""
    by_text: dict[str, list[tuple[str, str]]] = {}
    for split in sorted(Path(path).glob("*.parquet")):
        for r in pq.read_table(split, columns=["input", "output"]).to_pylist():
            query, _, transcript = r["input"].partition("\n")
            by_text.setdefault(transcript, []).append((query.strip(), r["output"] or ""))
    return [Meeting(hashlib.sha256(t.encode()).hexdigest()[:12],
                    tuple((m.group(1), m.group(2)) for line in t.splitlines() if (m := TURN.match(line))),
                    tuple(dict.fromkeys(qs))) for t, qs in by_text.items()]


def segments(m: Meeting) -> list[Message]:
    """The meeting as consecutive items of whole turns; speakers stand in the recipients, so people filters work."""
    parts: list[list[tuple[str, str]]] = [[]]
    for speaker, words in m.turns:
        if parts[-1] and sum(len(s) + len(w) + 3 for s, w in parts[-1]) + len(words) > SEGMENT_CHARS:
            parts.append([])
        parts[-1].append((speaker, words))
    return [Message(f"qmsum/{m.id}/{i:03d}", "meetings", None, "meeting",
                    tuple(dict.fromkeys(s.lower() for s, _ in part)), (), f"Meeting {m.id}",
                    "\n".join(f"{s}: {w}" for s, w in part)) for i, part in enumerate(parts) if part]
