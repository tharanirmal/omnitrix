"""Text helpers used by ingestion and recall - all plain code, no model."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have how i if in into is it its
me my of on or our should so than that the their them then there these they this to us was we were what
when where which who whom why will with would you your about any all also just please
""".split())


def estimate_tokens(text: str) -> int:
    """Rough token count (about 4 characters per token for English)."""
    return math.ceil(len(text) / 4)


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def chunk_text(text: str, max_chars: int = 900) -> list[str]:
    """Split on blank lines and pack paragraphs into chunks of at most `max_chars`; a paragraph that is
    longer than that is split at sentence ends."""
    paragraphs = [p.strip() for p in normalize(text).split("\n\n") if p.strip()]
    pieces: list[str] = []
    for p in paragraphs:
        if len(p) <= max_chars:
            pieces.append(p)
            continue
        sentence_buf = ""
        for sentence in re.split(r"(?<=[.!?])\s+", p):
            if sentence_buf and len(sentence_buf) + len(sentence) + 1 > max_chars:
                pieces.append(sentence_buf)
                sentence_buf = ""
            sentence_buf = f"{sentence_buf} {sentence}".strip()
            while len(sentence_buf) > max_chars:          # one enormous "sentence"
                pieces.append(sentence_buf[:max_chars])
                sentence_buf = sentence_buf[max_chars:]
        if sentence_buf:
            pieces.append(sentence_buf)

    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if buf and len(buf) + len(piece) + 2 > max_chars:
            chunks.append(buf)
            buf = ""
        buf = f"{buf}\n\n{piece}" if buf else piece
    if buf:
        chunks.append(buf)
    return chunks


def keyword_tsquery(query: str) -> str | None:
    """An OR query for to_tsquery('english', ...): natural questions rarely contain every word of the answer."""
    words: list[str] = []
    for w in re.findall(r"[a-z0-9]+", query.lower()):
        if len(w) >= 2 and w not in STOPWORDS and w not in words:
            words.append(w)
    return " | ".join(words) or None


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


# ------------------------------------------------------------------------------------------ entities

@dataclass(frozen=True)
class EntityRef:
    id: str
    name: str
    type: str
    self_: bool = False     # the user and their own company - mentioned everywhere, never used to scope


class EntityMatcher:
    """Finds known people, organizations and projects in text by name, alias, email address and domain.

    Longest match wins, so "Mehta Traders" is the organization and a lone "Mehta" is the person.
    Short aliases (under 4 characters, e.g. "RK") only match with exact case."""

    def __init__(self, rows: list[dict]):
        self.entities: dict[str, EntityRef] = {}
        self.by_email: dict[str, str] = {}
        self.by_domain: dict[str, str] = {}
        terms: list[tuple[str, str]] = []
        for r in rows:
            details = r.get("details") or {}
            self.entities[r["id"]] = EntityRef(r["id"], r["name"], r["type"], bool(details.get("self")))
            for term in {r["name"], *(r.get("aliases") or [])}:
                if term:
                    terms.append((term, r["id"]))
            if details.get("email"):
                self.by_email[details["email"].lower()] = r["id"]
            if details.get("domain"):
                self.by_domain[details["domain"].lower()] = r["id"]
        terms.sort(key=lambda t: -len(t[0]))
        self._patterns = [
            (re.compile(rf"(?<![\w]){re.escape(term)}(?![\w])", 0 if len(term) < 4 else re.IGNORECASE), eid)
            for term, eid in terms
        ]

    def find(self, text: str) -> list[str]:
        """Entity ids mentioned in `text`, in order of first appearance."""
        taken: list[tuple[int, int]] = []
        found: dict[str, int] = {}
        for pattern, eid in self._patterns:            # longest terms first
            for m in pattern.finditer(text):
                s, e = m.span()
                if any(s < te and ts < e for ts, te in taken):
                    continue
                taken.append((s, e))
                found.setdefault(eid, s)
        return sorted(found, key=found.get)

    def for_address(self, address: str) -> list[tuple[str, str]]:
        """(entity_id, how) for an email address: the person, and the organization owning the domain."""
        address = address.lower()
        out = []
        if address in self.by_email:
            out.append((self.by_email[address], "address"))
        domain = address.rsplit("@", 1)[-1]
        if domain in self.by_domain:
            out.append((self.by_domain[domain], "domain"))
        return out

    def is_self(self, entity_id: str) -> bool:
        ref = self.entities.get(entity_id)
        return bool(ref and ref.self_)
