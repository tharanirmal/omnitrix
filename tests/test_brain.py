import hashlib
import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from omnitrix.brain.connectors import RawDoc
from omnitrix.brain.ingest import Ingestor
from omnitrix.brain.recall import Brain
from omnitrix.brain.text import EntityMatcher, chunk_text, keyword_tsquery
from omnitrix.demo import load_world

TZ = ZoneInfo("Asia/Kolkata")

ENTITY_ROWS = [
    {"id": "ent_mehta", "name": "Rajesh Mehta", "type": "person", "aliases": ["Mehta", "Rajesh ji"],
     "details": {"email": "rajesh@mehtatraders.example"}},
    {"id": "ent_mehtatraders", "name": "Mehta Traders", "type": "organization", "aliases": [],
     "details": {"domain": "mehtatraders.example"}},
    {"id": "ent_ravi", "name": "Ravi Kumar", "type": "person", "aliases": ["RK"], "details": {"self": True}},
]


def test_chunking_packs_paragraphs_and_splits_long_ones():
    text = "\n\n".join(["short paragraph"] * 3 + ["x. " * 700])
    chunks = chunk_text(text, max_chars=300)
    assert chunks[0].startswith("short paragraph\n\nshort paragraph")
    assert all(len(c) <= 300 for c in chunks)
    assert "".join(chunks).count("x.") == 700


def test_longest_match_wins_and_short_aliases_need_exact_case():
    m = EntityMatcher(ENTITY_ROWS)
    assert m.find("Mehta Traders sent a PO") == ["ent_mehtatraders"]
    assert m.find("Rajesh ji called; Mehta Traders too") == ["ent_mehta", "ent_mehtatraders"]
    assert m.find("RK agreed") == ["ent_ravi"] and m.find("the rk file") == []
    assert m.for_address("Rajesh@MehtaTraders.example") == [("ent_mehta", "address"), ("ent_mehtatraders", "domain")]
    assert m.is_self("ent_ravi") and not m.is_self("ent_mehta")


def test_keyword_query_drops_stopwords_and_uses_or():
    assert keyword_tsquery("What is blocking the quote for Mehta?") == "blocking | quote | mehta"
    assert keyword_tsquery("what is it?") is None


def fake_embed_one(text: str, dim: int = 1024) -> list[float]:
    """Hashed bag of words: texts sharing words get similar vectors - enough to test ranking offline."""
    v = [0.0] * dim
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


async def fake_embed(texts: list[str]) -> list[list[float]]:
    return [fake_embed_one(t) for t in texts]


class ListConnector:
    def __init__(self, docs):
        self.docs = docs

    async def fetch(self):
        for d in self.docs:
            yield d


def email(i, subject, body, sender=("Rajesh Mehta", "rajesh@mehtatraders.example"), reply_to=None):
    return RawDoc(kind="email", location=f"test://{i}", received_at=datetime(2026, 10, 5, 9, i, tzinfo=TZ),
                  title=subject, doc_type="email", text=body, meta={"demo_id": f"t{i}"},
                  message_id=f"<t{i}@x.example>", in_reply_to=reply_to, from_name=sender[0], from_addr=sender[1],
                  to=[("Ravi Kumar", "ravi@suryodayafoods.example")])


@pytest.mark.db
async def test_ingest_links_entities_is_idempotent_and_recall_stays_in_scope(db, clock):
    await load_world(db, TZ)
    docs = [
        email(1, "Q4 order - revised quote", "Please send the revised quote by Thursday evening."),
        email(2, "Re: Q4 order - revised quote", "Thanks Ravi, Thursday works.", reply_to="<t1@x.example>"),
        email(3, "Price revision", "Prices go up 6% from November.", sender=("Farhan Ali", "farhan@greenpack.example")),
        email(4, "Newsletter", "Festive demand is rising across snack categories.",
              sender=("Digest", "digest@news.example")),
    ]
    ingestor = Ingestor(db, fake_embed, clock)
    stats = await ingestor.ingest([ListConnector(docs)])
    assert (stats.new_sources, stats.documents, stats.links) == (4, 4, 1)
    again = await ingestor.ingest([ListConnector(docs)])
    assert (again.new_sources, again.skipped) == (0, 4)

    linked = await db.fetch("SELECT d.meta->>'demo_id' AS demo, m.entity_id, m.how FROM mentions m "
                            "JOIN documents d ON d.id = m.document_id WHERE d.meta->>'demo_id' = 't1' ORDER BY 2, 3")
    assert {(r["entity_id"], r["how"]) for r in linked} >= {("ent_mehta", "sender"), ("ent_mehtatraders", "domain")}

    brain = Brain(db, fake_embed, clock)
    pack = await brain.recall("When does Mehta want the revised quote?", k=3)
    assert [e["id"] for e in pack.entities] == ["ent_mehta"]
    assert pack.stats["scoped"] and pack.stats["scope_documents"] == 2
    assert {i.ref["demo_id"] for i in pack.items} == {"t1", "t2"}      # never the vendor mail or the newsletter
    assert any(f.text == "Rajesh Mehta works at Mehta Traders" for f in pack.facts)
    assert "Sources:" in pack.to_prompt()

    logged = await db.fetchrow("SELECT query, entity_ids, stats FROM recall_log ORDER BY recorded_at DESC LIMIT 1")
    assert logged["entity_ids"] == ["ent_mehta"] and logged["stats"]["returned_chunks"] == len(pack.items)


@pytest.mark.db
async def test_questions_without_names_search_everything_and_bring_decisions(db, clock):
    await load_world(db, TZ)
    await Ingestor(db, fake_embed, clock).ingest([ListConnector([
        email(1, "Vendor idea", "FreshWrap is cheaper for packaging.", sender=("Meera Iyer", "meera@suryodayafoods.example")),
    ])])
    pack = await Brain(db, fake_embed, clock).recall("What did we decide about new vendors this quarter?")
    assert not pack.stats["scoped"]
    assert any(f.ref == "decisions:dec_02" for f in pack.facts)


@pytest.mark.db
async def test_scale_test_documents_can_be_removed_cleanly(db, clock):
    from omnitrix.brain.noise import NoiseConnector, remove_noise

    await load_world(db, TZ)
    await Ingestor(db, fake_embed, clock).ingest([ListConnector([email(1, "Real", "Keep me.")])])
    stats = await Ingestor(db, fake_embed, clock).ingest([NoiseConnector(5, clock.now())])
    assert stats.documents == 5
    assert await remove_noise(db) == 5
    left = await db.fetchrow(
        "SELECT (SELECT count(*) FROM documents) AS docs, (SELECT count(*) FROM sources WHERE location LIKE 'noise://%%') "
        "AS noise_sources, (SELECT count(*) FROM events WHERE type = 'document.ingested') AS doc_events")
    assert (left["docs"], left["noise_sources"], left["doc_events"]) == (1, 0, 1)
