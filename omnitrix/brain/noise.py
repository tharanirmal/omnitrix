"""Scale test: flood the brain with fictional look-alike documents ("hard negatives") - quotes, price rises,
vendor debates, loan paperwork, candidates, investor updates - about *other* people and companies.

They share vocabulary with the real questions but never name Ravi's people, companies or projects, so a
good brain should keep finding the right sources while reading only a small part of a much larger store.
Everything is marked `meta.synthetic_noise = true` and can be removed again."""
from __future__ import annotations

import random
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from omnitrix.core.db import Database

from .connectors import RawDoc

FIRST = ["Amit", "Sunita", "Karan", "Divya", "Manoj", "Pooja", "Suresh", "Anjali", "Vivek", "Rekha", "Harish",
         "Nandini", "Gaurav", "Shalini", "Prakash", "Leela", "Tarun", "Bhavna", "Ramesh", "Geeta"]
LAST = ["Sharma", "Verma", "Reddy", "Pillai", "Banerjee", "Chopra", "Desai", "Joshi", "Malhotra", "Naidu", "Bose",
        "Kulkarni", "Saxena", "Agarwal", "Rao Iyer", "Fernandes"]
COMPANIES = ["Sharma Distributors", "Northstar Retail", "Coastline Foods", "Bluepeak Traders", "Annapurna Stores",
             "Metro Mart Wholesale", "Evergreen Agro", "Sunrise Retail Chain", "Deccan Provisions", "Konkan Foods"]
VENDORS = ["PaperCo Packaging", "BoxWorks", "PrintPak Industries", "FlexiFilm Laminates", "CartonCraft"]
BANKS = ["Western Coast Bank", "Sahyadri Co-op Bank", "Unity Commercial Bank"]
FUNDS = ["Banyan Capital", "Summit Growth Partners", "Riverbend VC"]
ITEMS = ["peanut chikki", "roasted chana", "murukku", "khakhra", "rice crackers", "salted cashews", "mixture"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

TEMPLATES = [
    ("Revised quote for {company}", "Hi {first},\n\nCould you send the revised quote for {n} cartons of {item} by {day}? "
     "We need it before finalising our festive stock.\n\nRegards,\n{sender}"),
    ("Costing update - {company} order", "The costing for the {company} order is delayed because {item} prices went "
     "up again. I'll share the numbers by {day}.\n\n{sender}"),
    ("Price revision from {vendor}", "Dear customer,\n\n{vendor} will revise prices by {pct}% on all cartons from next "
     "month due to paper costs. Please acknowledge.\n\n{sender}"),
    ("New vendor proposal - {vendor}", "Team, {vendor} quoted {pct}% cheaper for our festive packs. Should we switch "
     "vendors this quarter? The decision is pending with management.\n\n{sender}"),
    ("{bank} - renewal documents", "Dear {first},\n\nFor the renewal of your cash credit limit please submit audited "
     "financials and the stock statement by the {date}th.\n\n{sender}, {bank}"),
    ("Candidates for the regional manager role", "Hi, three candidates are shortlisted for the regional manager role: "
     "{name1}, {name2} and {name3}. Please pick two for interviews by {day}.\n\n{sender}"),
    ("{fund} - quarterly investor update", "Dear founders, please send your Q2 numbers and the updated deck before our "
     "partner meeting on {day}. We are raising a new fund.\n\n{sender}, {fund}"),
    ("Machine delivery update", "The packing machine for our new line is delayed by {n2} weeks because of a parts "
     "shortage. We need to decide on extra shifts by {day}.\n\n{sender}"),
    ("Discount request from {company}", "{company} is asking for a {pct}% discount on their festive order. What is the "
     "maximum discount we can offer on orders this size?\n\n{sender}"),
    ("Weekly sales report", "Sorry, the weekly sales report will be late again - stuck with a distributor dispute in "
     "{city}. Will send it tomorrow.\n\n{sender}"),
    ("Anniversary plans", "Don't forget dinner on {day} evening - please keep it free after 7!\n\n{sender}"),
    ("GST catch-up", "Let's catch up next week to review the GST numbers before the filing on the 20th.\n\n{sender}"),
]
CITIES = ["Pune", "Coimbatore", "Hyderabad", "Nagpur", "Kochi", "Indore"]


def _name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def make_noise(n: int, start: datetime, seed: int = 7) -> list[RawDoc]:
    rng = random.Random(seed)
    docs = []
    for i in range(n):
        subject, body = TEMPLATES[i % len(TEMPLATES)]
        fields = {"company": rng.choice(COMPANIES), "vendor": rng.choice(VENDORS), "bank": rng.choice(BANKS),
                  "fund": rng.choice(FUNDS), "item": rng.choice(ITEMS), "day": rng.choice(DAYS),
                  "n": rng.randrange(200, 3000, 50), "n2": rng.randint(2, 6), "pct": rng.randint(3, 15),
                  "date": rng.randint(10, 28), "first": rng.choice(FIRST), "sender": _name(rng),
                  "name1": _name(rng), "name2": _name(rng), "name3": _name(rng), "city": rng.choice(CITIES)}
        docs.append(RawDoc(kind="manual", location=f"noise://{seed}/{i}",
                           received_at=start - timedelta(hours=rng.randint(1, 24 * 60)),
                           title=subject.format(**fields), doc_type="email", text=body.format(**fields),
                           meta={"synthetic_noise": True}, from_name=fields["sender"]))
    return docs


class NoiseConnector:
    def __init__(self, n: int, start: datetime, seed: int = 7):
        self.docs = make_noise(n, start, seed)

    async def fetch(self) -> AsyncIterator[RawDoc]:
        for d in self.docs:
            yield d


async def remove_noise(db: Database) -> int:
    async with db.connection() as conn, conn.transaction():
        rows = await (await conn.execute(
            "SELECT id, source_id FROM documents WHERE (meta->>'synthetic_noise')::boolean")).fetchall()
        doc_ids = [r["id"] for r in rows]
        source_ids = list({r["source_id"] for r in rows})
        # the source events and the document.ingested events they caused go together, in one statement,
        # so the caused_by references never dangle
        event_ids = [r["id"] for r in await (await conn.execute(
            "SELECT id FROM events WHERE (subject_kind = 'source' AND subject_id = ANY(%s)) "
            "OR (subject_kind = 'document' AND subject_id = ANY(%s))", (source_ids, doc_ids))).fetchall()]
        await conn.execute("DELETE FROM event_deliveries WHERE event_id = ANY(%s)", (event_ids,))
        await conn.execute("DELETE FROM events WHERE id = ANY(%s)", (event_ids,))
        await conn.execute("DELETE FROM documents WHERE id = ANY(%s)", (doc_ids,))
        await conn.execute("DELETE FROM sources WHERE id = ANY(%s)", (source_ids,))
    # clear the deleted rows out of the vector index now; until autovacuum runs, HNSW keeps visiting them
    # and nearest-neighbour searches come back short
    async with db.connection() as conn:
        await conn.set_autocommit(True)
        await conn.execute("VACUUM ANALYZE chunks")
        await conn.set_autocommit(False)
    return len(doc_ids)
