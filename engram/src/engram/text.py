"""Plain-code text handling for messages: separate what a message says from the history it quotes,
thread keys, content hashes, retrieval headers and chunking. No models here (LR §3.2: structure is code)."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import datetime

# Where quoted or forwarded history begins, in the styles seen in business email (Outlook, Lotus Notes, plain).
_QUOTE_START = re.compile(
    r"""^(?:
        [ \t]*-{2,}[ \t]*Original[ \t]Message[ \t]*-{2,}                       # Outlook reply
      | [ \t]*-{5,}[ \t]*Forwarded[ \t]by\b                                   # Lotus Notes forward banner
      | [ \t]*-{3,}[ \t]*Forwarded[ \t]message[ \t]*-{3,}                     # Gmail-style forward
      | [ \t]*Begin[ \t]forwarded[ \t]message:
      | [^\n]{1,160}[ \t]on[ \t]\d{1,2}/\d{1,2}/\d{2,4}[ \t]\d{1,2}:\d{2}(?::\d{2})?[ \t]?[AP]M[ \t]*\n
          (?:[^\n]*\n){0,2}[ \t]*To:                                          # Lotus reply: "X on 01/10/2000 11:23 AM"
      | [^\n]{1,80}\n[ \t]*\d{1,2}/\d{1,2}/\d{2,4}[ \t]\d{1,2}:\d{2}(?::\d{2})?[ \t]?[AP]M[ \t]*\n
          [ \t]*To:                                                           # Lotus reply: name / date / To: lines
      | [ \t]*From:[ \t][^\n]+\n[ \t]*(?:Sent|Date):[ \t]                     # bare header block
      | [ \t]*>[^\n]*\n[ \t]*>                                                 # 2+ '>'-quoted lines (a lone '>'
    )""",                                                                     # line is often mbox '>From' or HTML)
    re.MULTILINE | re.VERBOSE | re.IGNORECASE,
)
_SUBJECT_PREFIX = re.compile(r"^\s*(?:(?:re|fw|fwd|aw|sv)\s*(?:\[\d+\])?\s*:\s*)+", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WS = re.compile(r"\s+")


def split_quoted(body: str) -> tuple[str, str]:
    """(what the message itself says, the quoted/forwarded history below it)."""
    body = (body or "").replace("\r\n", "\n")
    m = _QUOTE_START.search(body)
    if m is None:
        return body.strip(), ""
    return body[: m.start()].strip(), body[m.start():].strip()


def thread_key(subject: str) -> str:
    """Subject without reply/forward prefixes, lower-cased: messages of one thread share it."""
    return _WS.sub(" ", _SUBJECT_PREFIX.sub("", subject or "")).strip().lower()


def content_hash(*parts: object) -> str:
    """Stable identity for a message: identical copies (e.g. one email kept in two folders) share it."""
    joined = "\x1f".join(_WS.sub(" ", "" if p is None else str(p)).strip() for p in parts)
    return hashlib.sha256(joined.encode()).hexdigest()


def header(sent_at: datetime | None, sender: str, recipients: Sequence[str], subject: str) -> str:
    """A one-line context prefix embedded and searched with every chunk, so a chunk is findable by who, when
    and subject even when its text never repeats them (a cheap, deterministic form of contextual retrieval)."""
    when = f"{sent_at:%Y-%m-%d}" if sent_at else "undated"
    to = ", ".join(recipients[:3]) + (f" +{len(recipients) - 3}" if len(recipients) > 3 else "")
    return f"{when} | From: {sender} | To: {to} | Subject: {subject}"


def chunk(text: str, max_chars: int = 1200) -> list[str]:
    """Pack paragraphs into chunks of at most max_chars; split long paragraphs at sentence ends."""
    pieces: list[str] = []
    for para in (p.strip() for p in re.split(r"\n\s*\n", text or "")):
        if not para:
            continue
        if len(para) <= max_chars:
            pieces.append(para)
            continue
        buf = ""
        for sentence in _SENTENCE_END.split(para):
            while len(sentence) > max_chars:                     # one enormous "sentence" (tables, links)
                if buf:
                    pieces.append(buf)
                    buf = ""
                pieces.append(sentence[:max_chars])
                sentence = sentence[max_chars:]
            if buf and len(buf) + 1 + len(sentence) > max_chars:
                pieces.append(buf)
                buf = ""
            buf = f"{buf} {sentence}".strip()
        if buf:
            pieces.append(buf)

    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if buf and len(buf) + 2 + len(piece) > max_chars:
            chunks.append(buf)
            buf = ""
        buf = f"{buf}\n\n{piece}" if buf else piece
    if buf:
        chunks.append(buf)
    return chunks
