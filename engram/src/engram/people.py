"""People as entities (handoff W4): one row per person with every address and name they appear under, so an agent
can ask about "Shirley" and the brain knows it means shirley.crenshaw@enron.com, and belief chains about "Vince"
and "Vince Kaminski" are one person. S0 rules only: the owner's sending addresses are one person; first.last
addresses name a person; an initial-plus-surname address (vkaminski@aol.com) joins the one person it fits; names in
beliefs become aliases when they fit exactly one well-known person. Rebuilt from scratch: cheap and idempotent."""
from __future__ import annotations

import re
from collections import Counter

import psycopg

from .index import _like_literal

WORD = re.compile(r"[a-z]+")


def build(conn: psycopg.Connection, mailbox: str = "") -> int:
    """Rebuild `people`. `mailbox` (the owner's id, e.g. 'kaminski-v') becomes one of the owner's aliases: older
    memory builds told the extractor the owner's name was the mailbox id, and beliefs use it."""
    counts: Counter[str] = Counter()
    for r in conn.execute("SELECT from_addr, to_addrs, cc_addrs, direction FROM items WHERE kind <> 'meeting'"):
        if r["direction"] == "in":
            counts[r["from_addr"]] += 1
        else:
            counts.update(a for a in (*r["to_addrs"], *r["cc_addrs"]))
    owner = {r["from_addr"] for r in conn.execute("SELECT DISTINCT from_addr FROM items WHERE direction = 'out'")}
    people: dict[str, dict] = {}                        # key -> {name, addresses, aliases, n}

    def add(key: str, name: str, addr: str, n: int) -> None:
        p = people.setdefault(key, {"name": name, "addresses": set(), "aliases": set(), "n": 0})
        p["addresses"].add(addr)
        p["n"] += n

    single: list[tuple[str, int]] = []
    for addr, n in counts.items():
        if "@" not in addr or addr in owner:
            continue
        local = addr.split("@")[0]
        parts = [w for w in re.split(r"[._\-]+", local) if w.isalpha()]
        if len(parts) >= 2 and len(parts[0]) > 1 and len(parts[-1]) > 1:
            add(f"{parts[0]} {parts[-1]}", f"{parts[0].title()} {parts[-1].title()}", addr, n)
        else:
            single.append((addr, n))
    if owner:
        top = max(owner, key=lambda a: counts.get(a, 0))
        parts = [w for w in re.split(r"[._\-]+", top.split("@")[0]) if w.isalpha()]
        key = " ".join(parts[:1] + parts[-1:]) if len(parts) >= 2 else top
        for a in owner:
            add(key, key.title(), a, counts.get(a, 0))
        people[key]["aliases"] |= {"owner", "me"} | ({mailbox.lower()} if mailbox else set())
    by_last: dict[tuple[str, str], list[str]] = {}
    for key in people:
        w = key.split()
        if len(w) == 2:
            by_last.setdefault((w[0][0], w[1]), []).append(key)
    for addr, n in single:                              # vkaminski@aol.com -> the one 'v... kaminski'
        local = re.sub(r"[^a-z]", "", addr.split("@")[0])
        fits = [k for (i, last), ks in by_last.items() if len(local) > 3 and local == i + last for k in ks]
        if len(fits) == 1:
            add(fits[0], people[fits[0]]["name"], addr, n)
        else:
            add(addr, addr, addr, n)
    _aliases(conn, people)
    conn.execute("TRUNCATE people RESTART IDENTITY")
    with conn.cursor().copy("COPY people (name, key, addresses, aliases, n_items) FROM STDIN") as cp:
        for key, p in people.items():
            cp.write_row((p["name"], key, sorted(p["addresses"]), sorted(p["aliases"]), p["n"]))
    conn.commit()
    return len(people)


def _aliases(conn: psycopg.Connection, people: dict[str, dict]) -> None:
    """Names beliefs use ('shirley', 'anita l. dupont') attached to the one well-known person they fit."""
    known = {k: p for k, p in people.items() if p["n"] >= 3 and " " in k}
    by_first: dict[str, list[str]] = {}
    for k in known:
        by_first.setdefault(k.split()[0], []).append(k)
    names = {r["n"] for r in conn.execute("SELECT DISTINCT lower(actor) AS n FROM beliefs UNION "
                                          "SELECT DISTINCT lower(other) FROM beliefs")}
    for name in names:
        words = WORD.findall(name)
        if not words or "@" in name:
            continue
        key = f"{words[0]} {words[-1]}"
        if len(words) >= 2 and key in people:
            people[key]["aliases"].add(name)
        elif len(words) == 1 and len(by_first.get(words[0], [])) == 1:
            people[by_first[words[0]][0]]["aliases"].add(name)


def find(conn: psycopg.Connection, who: str, limit: int = 5) -> list[dict]:
    """People matching a name, alias or address fragment, the most frequent correspondents first."""
    w = who.strip().lower()
    p = f"%{_like_literal(w)}%"
    return conn.execute(
        "SELECT name, addresses, aliases, n_items FROM people WHERE key LIKE %(p)s OR lower(name) LIKE %(p)s "
        "OR %(w)s = ANY(aliases) OR EXISTS (SELECT 1 FROM unnest(addresses) a WHERE a LIKE %(p)s) "
        "ORDER BY n_items DESC LIMIT %(k)s", {"p": p, "w": w, "k": limit}).fetchall()
