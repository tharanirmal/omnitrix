"""QMSum meetings: grouping queries by transcript, spotting AMI product meetings, segmenting into items."""
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from engram.db import connect
from engram.sources import qmsum
from engram.store import ingest_messages

AMI = "\n".join(["Project Manager: Okay, let's decide on the case.", "Industrial Designer: I'd go with rubber.",
                 "Marketing: Rubber fits the spongy trend.", "User Interface: Fine by me.",
                 "Project Manager: Decided then, rubber case. I'll send the minutes."] * 20)
COMMITTEE = "Chair: Welcome to the committee.\nWitness: Thank you, chair."


def read(tmp_path):
    rows = [{"input": f"What was decided about the case?\n{AMI}", "output": "They chose rubber."},
            {"input": f"Summarize the meeting.\n{AMI}", "output": ""},
            {"input": f"Summarize the meeting.\n{COMMITTEE}", "output": "A welcome."}]
    pq.write_table(pa.Table.from_pylist(rows), tmp_path / "train.parquet")
    return qmsum.read_meetings(tmp_path)


def test_meetings_group_queries_and_segment_by_whole_turns(tmp_path):
    meetings = read(tmp_path)
    ami = next(m for m in meetings if m.is_ami)
    assert len(meetings) == 2 and not next(m for m in meetings if not m.is_ami).is_ami
    assert ami.queries == (("What was decided about the case?", "They chose rubber."), ("Summarize the meeting.", ""))
    parts = qmsum.segments(ami)
    assert len(parts) > 1 and all(len(p.body) <= qmsum.SEGMENT_CHARS for p in parts)
    assert "\n".join(p.body for p in parts) == AMI                               # nothing lost, no turn split
    assert {p.subject for p in parts} == {f"Meeting {ami.id}"} and parts[0].to_addrs[0] == "project manager"


@pytest.mark.db
def test_meeting_segments_ingest_as_one_undated_conversation(db_url, tmp_path):
    parts = qmsum.segments(next(m for m in read(tmp_path) if m.is_ami))
    with connect(db_url) as conn:
        ingest_messages(conn, parts, set(), "qmsum", "meeting")
        rows = conn.execute("SELECT DISTINCT kind, thread_key, direction, sent_at FROM items").fetchall()
    assert len(rows) == 1 and rows[0]["kind"] == "meeting" and rows[0]["sent_at"] is None
