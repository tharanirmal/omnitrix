"""Bridge between the brain's graph and graphify (community detection, hub nodes, cohesion).

graphify is installed as its own tool (`uv tool install graphifyy`), not as a project dependency - it pulls in
~30 tree-sitter parsers the brain never needs. `run_graphify` exports the Brain Map graph in graphify's
extraction format, runs graphify_pipeline.py with graphify's interpreter, and `load_analysis` reads the result
back so the Brain Map can draw clusters and hubs. Everything stays on this machine.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

PIPELINE = Path(__file__).with_name("graphify_pipeline.py")
ENTITY_SOURCE = "demo_data/entities.yaml"
DECISION_SOURCE = "demo_data/decisions.yaml"
FINGERPRINT = ".omnitrix_fingerprint"
HEALTH_FLAGS = ("missing_endpoint_edges", "dangling_endpoint_edges", "self_loop_edges",
                "undirected_same_endpoint_collapsed_edges")
EDGE_RELATION = {"mention": "mentions", "decided_in": "decided_in", "decided_by": "decided_by",
                 "reply_to": "reply_to", "attachment_of": "attachment_of"}


class GraphifyUnavailable(RuntimeError):
    pass


def _source_file(node: dict) -> str:
    """graphify treats a node whose source has no file extension as an injected concept and leaves it out of
    the hub ranking, so every node points at the real file it came from."""
    group, ref = node["group"], node.get("ref") or node["id"]
    if group in ("person", "organization", "project"):
        return ENTITY_SOURCE
    if group == "decision":
        return DECISION_SOURCE
    if group == "email":
        return f"mailpit/{ref}.eml"
    if group == "note":
        return f"vault/{ref}"
    return f"files/{ref}"


def _file_type(group: str) -> str:
    return "rationale" if group == "decision" else "document"


def to_extraction(data: dict) -> tuple[dict, dict]:
    """(extraction, detection) in graphify's formats, from export_graph(). Only edges the brain already holds
    are passed on, all EXTRACTED - graphify is used for structure, not to invent links."""
    nodes = [{"id": n["id"], "label": n.get("title") or n["label"], "file_type": _file_type(n["group"]),
              "source_file": _source_file(n), "source_location": None, "source_url": None, "captured_at": None,
              "author": None, "contributor": None, "brain_group": n["group"], "brain_self": bool(n.get("self"))} for n in data["nodes"]]
    known = {n["id"] for n in nodes}
    by_id = {n["id"]: n for n in nodes}
    edges = [{"source": e["s"], "target": e["t"],
              "relation": e.get("label", "").replace(" ", "_") if e["kind"] == "relation" else EDGE_RELATION[e["kind"]],
              "confidence": "EXTRACTED", "confidence_score": 1.0, "source_file": by_id[e["s"]]["source_file"],
              "source_location": None, "weight": 1.0}
             for e in data["edges"] if e["s"] in known and e["t"] in known and e["s"] != e["t"]]
    docs = [n for n in nodes if n["source_file"] not in (ENTITY_SOURCE, DECISION_SOURCE)]
    detection = {"total_files": len(docs) + 2, "total_words": 0, "scan_root": ".",
                 "files": {"document": sorted({n["source_file"] for n in nodes})}}
    return {"nodes": nodes, "edges": edges, "hyperedges": [], "input_tokens": 0, "output_tokens": 0}, detection


def graphify_python() -> str:
    """graphify's own interpreter, found the way the graphify skill does: from the `graphify` script's shebang."""
    exe = shutil.which("graphify")
    if not exe:
        raise GraphifyUnavailable("graphify is not installed - `uv tool install graphifyy`")
    shebang = Path(exe).read_text(errors="replace").splitlines()[0].removeprefix("#!").strip()
    if not shebang or not os.access(shebang, os.X_OK):
        raise GraphifyUnavailable(f"cannot find graphify's Python in {exe}")
    return shebang


def run_graphify(data: dict, workdir: Path) -> dict:
    """Write the extraction under workdir/graphify-out/, run the pipeline, return the analysis."""
    out = workdir / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    extraction, detection = to_extraction(data)
    (out / ".graphify_extract.json").write_text(json.dumps(extraction, ensure_ascii=False), encoding="utf-8")
    (out / ".graphify_detect.json").write_text(json.dumps(detection, ensure_ascii=False), encoding="utf-8")
    done = subprocess.run([graphify_python(), str(PIPELINE)], cwd=workdir, capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise RuntimeError(f"graphify pipeline failed:\n{done.stdout}\n{done.stderr}")
    analysis = load_analysis(workdir)
    analysis["log"] = done.stdout
    return analysis


def load_analysis(workdir: Path) -> dict | None:
    path = workdir / "graphify-out" / ".graphify_analysis.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fingerprint(data: dict) -> str:
    """Changes whenever a node, a link or a node's type changes - i.e. whenever the clusters could."""
    parts = sorted(f"n|{n['id']}|{n['group']}|{bool(n.get('self'))}" for n in data["nodes"])
    parts += sorted(f"e|{e['s']}|{e['t']}|{e['kind']}" for e in data["edges"])
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def clusters_for_map(data: dict, workdir: Path) -> dict:
    """graphify's view of the graph, for the Brain Map: clusters, hubs and a health line. Re-runs graphify only
    when the graph has changed since the last run; never fails the page - without graphify the map simply
    colours by type."""
    fp = fingerprint(data)
    marker = workdir / "graphify-out" / FINGERPRINT
    try:
        analysis = load_analysis(workdir)
        if analysis is None or not marker.exists() or marker.read_text() != fp:
            analysis = run_graphify(data, workdir)
            marker.write_text(fp)
    except (GraphifyUnavailable, RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        return {"available": False, "reason": str(exc).splitlines()[0]}

    known = {n["id"] for n in data["nodes"]}
    clusters, node_cluster, unlinked = [], {}, []
    for cid, members in sorted(analysis["communities"].items(), key=lambda kv: (-len(kv[1]), int(kv[0]))):
        members = [m for m in members if m in known]
        if len(members) < 2:
            unlinked += members
            continue
        index = len(clusters)
        clusters.append({"id": index, "label": analysis["labels"][cid], "size": len(members),
                         "cohesion": round(analysis["cohesion"][cid], 2), "members": members})
        for m in members:
            node_cluster[m] = index
    hubs = [{"id": g["id"], "label": g["label"], "degree": g["degree"]} for g in analysis["gods"] if g["id"] in known]
    health = analysis.get("health", {})
    return {"available": True, "fingerprint": fp, "clusters": clusters, "node_cluster": node_cluster,
            "unlinked": unlinked, "hubs": hubs,
            "health": {k: health.get(k, 0) for k in HEALTH_FLAGS},
            "report": str(workdir / "graphify-out" / "GRAPH_REPORT.md")}
