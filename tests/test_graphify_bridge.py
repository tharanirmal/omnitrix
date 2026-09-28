import shutil

import pytest

from omnitrix.brain import graphify_bridge
from omnitrix.brain.graphify_bridge import clusters_for_map, fingerprint, to_extraction

needs_graphify = pytest.mark.skipif(shutil.which("graphify") is None, reason="graphify is not installed")


def node(id, group, label=None, **extra):
    return {"id": id, "label": label or id, "group": group, **extra}


def two_worlds() -> dict:
    """Two groups that only link inside themselves, one company everyone works for, and a stray newsletter."""
    nodes = [
        node("ent_self", "organization", "Our Co", self=True), node("ent_ravi", "person", "Ravi", self=True),
        node("ent_mehta", "person", "Mehta"), node("ent_traders", "organization", "Mehta Traders"),
        node("ent_prj_q4", "project", "Q4 order"),
        node("doc_e02", "email", "Q4 quote", ref="e02"), node("doc_e03", "email", "Re: Q4 quote", ref="e03"),
        node("doc_q4", "note", "Q4 order note", ref="Projects/Q4 order.md"),
        node("ent_bank", "organization", "Kaveri Bank"), node("ent_deepa", "person", "Deepa"),
        node("ent_prj_loan", "project", "Loan renewal"),
        node("doc_e08", "email", "Renewal documents", ref="e08"),
        node("doc_chk", "attachment", "checklist.pdf", ref="checklist.pdf"),
        node("doc_news", "email", "Snack digest", ref="e30"),
        node("dec_01", "decision", "Decision: no new vendors"),
    ]
    links = [("ent_mehta", "ent_traders", "relation"), ("ent_prj_q4", "ent_traders", "relation"),
             ("doc_e02", "ent_mehta", "mention"), ("doc_e03", "ent_mehta", "mention"), ("doc_e03", "doc_e02", "reply_to"),
             ("doc_q4", "ent_prj_q4", "mention"), ("doc_q4", "ent_mehta", "mention"), ("doc_e02", "ent_prj_q4", "mention"),
             ("ent_deepa", "ent_bank", "relation"), ("ent_prj_loan", "ent_bank", "relation"),
             ("doc_e08", "ent_deepa", "mention"), ("doc_e08", "ent_prj_loan", "mention"),
             ("doc_chk", "doc_e08", "attachment_of"), ("doc_chk", "ent_bank", "mention"),
             ("ent_ravi", "ent_self", "relation"),
             ("doc_e02", "ent_ghost", "mention")]                     # points at a node that is not drawn
    edges = [{"s": s, "t": t, "kind": k, **({"label": "works at"} if k == "relation" else {})} for s, t, k in links]
    return {"nodes": nodes, "edges": edges}


def test_extraction_uses_real_source_files_and_only_links_the_brain_holds():
    extraction, detection = to_extraction(two_worlds())
    by_id = {n["id"]: n for n in extraction["nodes"]}
    assert by_id["ent_mehta"]["source_file"] == "demo_data/entities.yaml"
    assert by_id["doc_e02"]["source_file"] == "mailpit/e02.eml"
    assert by_id["doc_q4"]["source_file"] == "vault/Projects/Q4 order.md"
    assert by_id["dec_01"]["file_type"] == "rationale" and by_id["doc_chk"]["file_type"] == "document"
    # graphify drops nodes whose source has no extension from its hub ranking - every node needs one
    assert all("." in n["source_file"].rsplit("/", 1)[-1] for n in extraction["nodes"])
    assert by_id["ent_self"]["brain_self"] and not by_id["ent_mehta"]["brain_self"]
    assert {e["confidence"] for e in extraction["edges"]} == {"EXTRACTED"}
    assert not any(e["target"] == "ent_ghost" for e in extraction["edges"])
    assert len(extraction["edges"]) == 15 and detection["total_files"] > 0


def test_fingerprint_changes_only_when_the_graph_does():
    data = two_worlds()
    same = two_worlds()
    same["nodes"].reverse()
    assert fingerprint(data) == fingerprint(same)
    same["edges"].append({"s": "doc_news", "t": "ent_bank", "kind": "mention"})
    assert fingerprint(data) != fingerprint(same)


def test_map_still_works_without_graphify(tmp_path, monkeypatch):
    monkeypatch.setattr(graphify_bridge.shutil, "which", lambda _: None)
    result = clusters_for_map(two_worlds(), tmp_path)
    assert result == {"available": False, "reason": "graphify is not installed - `uv tool install graphifyy`"}


@pytest.mark.graphify
@needs_graphify
def test_graphify_finds_the_two_worlds_and_names_them_after_their_projects(tmp_path):
    data = two_worlds()
    result = clusters_for_map(data, tmp_path)
    assert result["available"], result
    by_label = {c["label"]: set(c["members"]) for c in result["clusters"]}
    assert set(by_label) >= {"Q4 order", "Loan renewal"}
    assert {"ent_mehta", "doc_e02", "doc_q4"} <= by_label["Q4 order"]
    assert {"ent_bank", "doc_e08", "doc_chk"} <= by_label["Loan renewal"]
    assert "doc_news" in result["unlinked"] and "dec_01" in result["unlinked"]
    assert result["hubs"][0]["id"] in {"ent_mehta", "ent_prj_q4", "ent_bank", "doc_e02"}
    assert not any(result["health"].values())
    assert (tmp_path / "graphify-out" / "GRAPH_REPORT.md").exists()

    # unchanged graph: served from the last run, graphify is not started again
    (tmp_path / "graphify-out" / ".graphify_analysis.json").touch()
    before = (tmp_path / "graphify-out" / ".graphify_analysis.json").stat().st_mtime_ns
    assert clusters_for_map(data, tmp_path)["clusters"] == result["clusters"]
    assert (tmp_path / "graphify-out" / ".graphify_analysis.json").stat().st_mtime_ns == before
