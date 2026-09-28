import asyncio
from zoneinfo import ZoneInfo

import httpx
import pytest
from test_brain import ListConnector, email, fake_embed

from omnitrix.brain.ingest import Ingestor
from omnitrix.brain.recall import Brain
from omnitrix.dashboard.app import create_app
from omnitrix.dashboard.recalls import RecallFeed
from omnitrix.demo import load_world

TZ = ZoneInfo("Asia/Kolkata")


def client(db) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(db, TZ)), base_url="http://dashboard")


async def ingest_mehta_thread(db, clock) -> None:
    await load_world(db, TZ)
    await Ingestor(db, fake_embed, clock).ingest([ListConnector([
        email(1, "Q4 order - revised quote", "Please send the revised quote by Thursday evening."),
        email(2, "Re: Q4 order - revised quote", "Thanks Ravi, Thursday works.", reply_to="<t1@x.example>"),
        email(3, "Price revision", "Prices go up 6% from November.", sender=("Farhan Ali", "farhan@greenpack.example")),
        email(4, "Newsletter", "Festive demand is rising across snack categories.",
              sender=("Digest", "digest@news.example")),
    ])])


@pytest.mark.db
async def test_api_returns_a_log_entry_with_its_chunks(db, clock):
    await ingest_mehta_thread(db, clock)
    brain = Brain(db, fake_embed, clock)
    await brain.recall("What did GreenPack say about prices?", agent="fact_checker")
    pack = await brain.recall("When does Mehta want the revised quote?", agent="planner", k=3)

    async with client(db) as api:
        listing = (await api.get("/api/recalls")).json()
        assert [e["agent"] for e in listing["items"]] == ["planner", "fact_checker"]      # newest first
        entry = listing["items"][0]
        assert entry["query"] == "When does Mehta want the revised quote?"
        assert entry["at_label"] == "Thu 08 Oct 08:55:00"                                # demo clock, not wall time

        assert [e["agent"] for e in (await api.get("/api/recalls", params={"agent": "planner"})).json()["items"]] \
            == ["planner"]
        assert (await api.get("/api/recalls", params={"since": "2026-10-08T09:00"})).json()["items"] == []
        assert len((await api.get("/api/recalls", params={"until": "2026-10-08T09:00"})).json()["items"]) == 2
        assert (await api.get("/api/recalls", params={"before": entry["id"]})).json()["items"][0]["agent"] \
            == "fact_checker"

        detail = (await api.get(f"/api/recalls/{entry['id']}")).json()
        assert [e["name"] for e in detail["entities"]] == ["Rajesh Mehta"]
        assert detail["search"]["scoped"] and detail["search"]["scope_documents"] == 2
        assert detail["search"]["corpus_documents"] == pack.stats["corpus_documents"]
        assert 0 < detail["search"]["share_documents"] < 1

        chunks = detail["chunks"]
        assert [c["chunk_id"] for c in chunks] == [i.chunk_id for i in pack.items]
        assert {c["source"]["value"] for c in chunks} == {"t1", "t2"}
        first = chunks[0]
        assert first["title"] == pack.items[0].title and first["doc_type"] == "email"
        assert first["source"]["kind"] == "demo_id" and first["text"] == pack.items[0].text
        assert first["why"] and any(w.startswith(("meaning", "keyword")) for w in first["why"])
        assert "Rajesh Mehta works at Mehta Traders" in [f["text"] for f in detail["facts"]]
        assert detail["cost"]["returned_tokens"] == pack.stats["returned_tokens"]
        assert detail["cost"]["total_ms"] > 0 and "embed_ms" in detail["cost"]["timings"]

        page = await api.get(f"/documents/{first['document_id']}", params={"chunk": first["chunk_id"]})
        assert page.status_code == 200 and 'class="doc-chunk hit"' in page.text

        assert (await api.get("/api/recalls/recall_missing")).status_code == 404
        assert (await api.get("/api/recalls", params={"since": "not a date"})).status_code == 422


@pytest.mark.db
async def test_log_viewer_still_shows_entries_whose_chunks_were_removed(db, clock):
    await ingest_mehta_thread(db, clock)
    pack = await Brain(db, fake_embed, clock).recall("When does Mehta want the revised quote?", k=3)
    await db.execute("DELETE FROM documents WHERE id = %s", (pack.items[0].document_id,))
    async with client(db) as api:
        rid = (await api.get("/api/recalls")).json()["items"][0]["id"]
        chunks = (await api.get(f"/api/recalls/{rid}")).json()["chunks"]
    assert chunks[0]["missing"] and chunks[0]["why"]
    assert not chunks[-1]["missing"]


@pytest.mark.db
async def test_new_recalls_reach_the_live_feed(db, clock):
    await ingest_mehta_thread(db, clock)
    feed = RecallFeed(db.url)
    queue = await feed.subscribe()
    try:
        await Brain(db, fake_embed, clock).recall("When does Mehta want the revised quote?", agent="planner")
        recall_id = await asyncio.wait_for(queue.get(), 5)
        latest = await db.fetchrow("SELECT id FROM recall_log ORDER BY recorded_at DESC LIMIT 1")
        assert recall_id == latest["id"]
    finally:
        await feed.stop()


@pytest.mark.db
async def test_brain_map_is_served_live_with_or_without_graphify(db, clock, tmp_path):
    await ingest_mehta_thread(db, clock)
    app = create_app(db, TZ, workdir=tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://dashboard") as api:
        page = await api.get("/brain-map")
    assert page.status_code == 200 and "Brain Map" in page.text
    assert '"graphify": {"available": ' in page.text                   # clusters, or the reason there are none
    assert "https://" not in page.text.split("<script>")[0]           # no stylesheet or font from the internet
