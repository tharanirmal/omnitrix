"""The demo world must stay consistent: every reference resolves and every planted scenario is really there."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from omnitrix import demo

TZ = ZoneInfo("Asia/Kolkata")
ENTS = demo.load_yaml("entities.yaml")
ALL_IDS = [e["id"] for g in ("people", "organizations", "projects") for e in ENTS[g]]
EMAILS = demo.emails()
BY_ID = {e["id"]: e for e in EMAILS}


def events_on(day: str) -> list[dict]:
    return [e for e in demo.expand_calendar(demo.load_yaml("calendar.yaml")) if e["start"].startswith(day)]


def overlaps(start: str, end: str, day_events: list[dict]) -> list[str]:
    s, e = datetime.fromisoformat(start), datetime.fromisoformat(end)
    return [ev["id"] for ev in day_events
            if datetime.fromisoformat(ev["start"]) < e and s < datetime.fromisoformat(ev["end"])]


def test_entity_ids_are_unique_and_relations_resolve():
    assert len(ALL_IDS) == len(set(ALL_IDS)) == 30
    for src, _, dst in ENTS["relations"]:
        assert src in ALL_IDS and dst in ALL_IDS


def test_calendar_references_and_ids():
    events = demo.expand_calendar(demo.load_yaml("calendar.yaml"))
    assert len({e["id"] for e in events}) == len(events) == 40
    for e in events:
        assert set(e.get("attendees", [])) <= set(ALL_IDS)
        assert e["end"] > e["start"]


def test_planted_calendar_situations():
    thursday = events_on("2026-10-08")
    assert overlaps("2026-10-08T17:00", "2026-10-08T17:30", thursday) == []            # S1: free at 5 PM
    assert overlaps("2026-10-08T11:30", "2026-10-08T12:00", thursday) == ["cal_0801"]  # S11: investor call
    friday = events_on("2026-10-09")
    assert overlaps("2026-10-09T20:30", "2026-10-09T21:30", friday) == ["cal_0904"]    # S2: anniversary
    assert not any(e["id"].startswith("rec_dinner") for e in friday)


def test_emails_are_well_formed():
    assert len(EMAILS) == len(BY_ID) == 36
    assert sum(e["stage"] == "live" for e in EMAILS) == 8
    for e in EMAILS:
        assert e["stage"] in ("inbox", "live")
        datetime.fromisoformat(e["at"])
        for person in [e["from"], *e["to"], *e.get("cc", [])]:
            assert person["email"].endswith(".example"), person
        for name in e.get("attachments", []):
            assert (demo.DATA / "documents" / name).exists(), name
        if e.get("in_reply_to"):
            parent = BY_ID[e["in_reply_to"]]
            assert parent["at"] < e["at"] and parent.get("thread") == e.get("thread")


def test_inbox_emails_arrive_before_the_demo_starts_and_live_ones_after():
    start = datetime.fromisoformat(demo.persona()["demo"]["clock_start"])
    for e in EMAILS:
        at = datetime.fromisoformat(e["at"])
        assert (at <= start) if e["stage"] == "inbox" else (at > start), e["id"]


def test_every_scenario_is_planted():
    voice = demo.load_yaml("voice-notes/voice_notes.yaml")["voice_notes"]
    planted = {e.get("scenario") for e in EMAILS} | {v.get("scenario") for v in voice}
    assert {f"S{i}" for i in range(1, 16) if i != 13} <= planted
    assert (demo.DATA / "outside-world" / "2026-10-07_labelling-rule.md").exists()        # S13
    assert BY_ID["L4"]["from"]["email"].split("@")[1] != demo.persona()["email"].split("@")[1]  # S9 look-alike
    assert "8%" not in BY_ID["e13"]["body"] and "6%" in BY_ID["e13"]["body"]                # S7: email says 6%


def test_referenced_files_exist():
    for d in demo.load_yaml("decisions.yaml")["decisions"]:
        if d["source"]:
            assert (demo.DATA / "obsidian-vault" / d["source"]).exists(), d["source"]
    for v in demo.load_yaml("voice-notes/voice_notes.yaml")["voice_notes"]:
        assert (demo.DATA / "voice-notes" / v["file"]).exists(), v["file"]


def test_test_set_shape():
    rows = {}
    for split, n in (("dev", 20), ("holdout", 10)):
        lines = (demo.DATA / "test-set" / f"{split}.jsonl").read_text().splitlines()
        assert len(lines) == n
        for line in lines:
            r = json.loads(line)
            assert r["split"] == split and r["id"] not in rows
            rows[r["id"]] = r
            datetime.fromisoformat(r["received_at"])
            for t in r["expected"]["tasks"]:
                if t["due_at"]:
                    datetime.fromisoformat(t["due_at"])


def test_threading_headers():
    msg = demo.build_message(BY_ID["L1"], BY_ID)
    assert msg["In-Reply-To"] == "<e25.demo@mehtatraders.example>"
    assert msg["References"].split() == ["<e02.demo@mehtatraders.example>", "<e03.demo@suryodayafoods.example>",
                                         "<e25.demo@mehtatraders.example>"]
    with_pdf = demo.build_message(BY_ID["L3"], BY_ID)
    assert [p.get_filename() for p in with_pdf.iter_attachments()] == ["invoice_quickpay_INV-4471.pdf"]


@pytest.mark.db
async def test_load_world_into_the_database(db):
    counts = await demo.load_world(db, TZ)
    assert counts == {"entities": 30, "relations": 41, "decisions": 4, "promise_history": 7, "calendar_events": 40}
    # the graph answers "what depends on Line 2?" for the Analyst (S14)
    rows = await db.fetch("SELECT e.name FROM relations r JOIN entities e ON e.id = r.from_entity "
                          "WHERE r.to_entity = 'ent_prj_line2' AND r.type = 'depends_on' ORDER BY e.name")
    assert [r["name"] for r in rows] == ["Mehta Q4 order", "Working capital renewal"]
    decision = await db.fetchrow("SELECT d.what, s.location FROM decisions d JOIN sources s ON s.id = d.source_id "
                                 "WHERE d.id = 'dec_02'")
    assert decision["location"] == "vault://Meetings/2026-09-22 Packaging review.md"
    late = await db.fetchrow("SELECT count(*) AS n FROM promises WHERE promiser = 'ent_rohit' "
                             "AND (history->0->>'at')::timestamptz > due_at")
    assert late["n"] == 3
