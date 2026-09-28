"""Export the brain as one self-contained, offline HTML page: how the data is connected, which clusters it
forms (graphify), and a replay of what each recall touched. No CDN, no network - it works with Wi-Fi off."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from omnitrix.core.db import Database

from .graphify_bridge import clusters_for_map

TEMPLATE = Path(__file__).with_name("graph_template.html")
WORKDIR = Path(__file__).resolve().parents[2] / "var"      # graphify-out/ is written here
SELF_IDS_SQL = "SELECT id FROM entities WHERE (details->>'self')::boolean IS TRUE"


def _short(text: str, n: int = 34) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


async def export_graph(db: Database) -> dict:
    self_ids = {r["id"] for r in await db.fetch(SELF_IDS_SQL)}
    nodes: list[dict] = []
    edges: list[dict] = []

    for e in await db.fetch("SELECT id, name, type, importance, details FROM entities ORDER BY id"):
        d = e["details"] or {}
        nodes.append({"id": e["id"], "label": e["name"], "group": e["type"], "self": e["id"] in self_ids,
                      "importance": e["importance"],
                      "info": {k: v for k, v in d.items() if k in ("role", "email", "summary", "value_inr", "type",
                                                                   "city", "note")}})

    # scale-test look-alike documents are counted but not drawn - thousands of dots would bury the picture
    docs = await db.fetch("SELECT d.id, d.title, d.doc_type, d.occurred_at, d.meta, left(d.full_text, 280) AS snippet, "
                          "(SELECT count(*) FROM chunks c WHERE c.document_id = d.id) AS chunks FROM documents d "
                          "WHERE NOT coalesce((d.meta->>'synthetic_noise')::boolean, false)")
    drawn = {d["id"] for d in docs}
    path_to_doc = {}
    for d in docs:
        meta = d["meta"] or {}
        group = ("email" if d["doc_type"] == "email" else
                 "attachment" if d["doc_type"] == "attachment" else
                 "pdf" if d["doc_type"] == "pdf" else "note")
        ref = meta.get("demo_id") or meta.get("path") or meta.get("filename") or ""
        if meta.get("path"):
            path_to_doc[meta["path"]] = d["id"]
        nodes.append({"id": d["id"], "label": _short(d["title"]), "title": d["title"], "group": group,
                      "doc_type": d["doc_type"], "ref": ref, "chunks": d["chunks"],
                      "date": d["occurred_at"].strftime("%a %d %b %H:%M") if d["occurred_at"] else "",
                      "from": meta.get("from_name"), "snippet": d["snippet"]})

    for dec in await db.fetch("SELECT d.id, d.what, d.decided_at, d.decided_by, s.location FROM decisions d "
                              "LEFT JOIN sources s ON s.id = d.source_id"):
        nodes.append({"id": dec["id"], "label": _short("Decision: " + dec["what"], 38), "title": dec["what"],
                      "group": "decision", "date": dec["decided_at"].strftime("%d %b %Y") if dec["decided_at"] else ""})
        path = (dec["location"] or "").removeprefix("vault://")
        if path in path_to_doc:
            edges.append({"s": dec["id"], "t": path_to_doc[path], "kind": "decided_in"})
        if dec["decided_by"] and dec["decided_by"] not in self_ids:
            edges.append({"s": dec["id"], "t": dec["decided_by"], "kind": "decided_by"})

    for r in await db.fetch("SELECT id, from_entity, to_entity, type FROM relations WHERE valid_to IS NULL"):
        edges.append({"s": r["from_entity"], "t": r["to_entity"], "kind": "relation", "label": r["type"].replace("_", " "),
                      "id": r["id"]})
    for m in await db.fetch("SELECT DISTINCT document_id, entity_id FROM mentions"):
        if m["entity_id"] not in self_ids and m["document_id"] in drawn:          # the user and their company are in everything - skip the hairball
            edges.append({"s": m["document_id"], "t": m["entity_id"], "kind": "mention"})
    for link in await db.fetch("SELECT from_doc, to_doc, type FROM document_links"):
        edges.append({"s": link["from_doc"], "t": link["to_doc"], "kind": link["type"]})

    traces = []
    rows = await db.fetch(
        "SELECT DISTINCT ON (query, strategy) query, strategy, agent, entity_ids, scope_docs, returned, facts, stats "
        "FROM recall_log ORDER BY query, strategy, recorded_at DESC")
    by_query: dict[str, dict] = {}
    for r in rows:
        entry = by_query.setdefault(r["query"], {"query": r["query"], "agent": r["agent"]})
        entry[r["strategy"]] = {
            "entities": r["entity_ids"], "scope_entities": (r["stats"] or {}).get("scope_entities", []),
            "scope_docs": r["scope_docs"], "returned": r["returned"],
            "facts": [f["ref"] for f in r["facts"]], "fact_text": [f["text"] for f in r["facts"]],
            "stats": r["stats"]}
    traces = [t for t in by_query.values() if "brain" in t and t["query"] != "warm-up"]

    counts = await db.fetchrow(
        "SELECT (SELECT count(*) FROM documents) AS documents, (SELECT count(*) FROM chunks) AS chunks, "
        "(SELECT count(*) FROM entities) AS entities, (SELECT count(*) FROM relations) AS relations, "
        "(SELECT count(*) FROM mentions) AS mentions, (SELECT count(*) FROM decisions) AS decisions, "
        "(SELECT count(*) FROM documents WHERE (meta->>'synthetic_noise')::boolean) AS noise_documents")
    return {"nodes": nodes, "edges": edges, "traces": traces, "counts": dict(counts)}


async def export_graph_with_clusters(db: Database, workdir: Path = WORKDIR) -> dict:
    """export_graph plus graphify's clusters and hubs (graphify runs in a subprocess, off the event loop)."""
    data = await export_graph(db)
    data["graphify"] = await asyncio.to_thread(clusters_for_map, data, workdir)
    return data


def render_html(data: dict) -> str:
    payload = json.dumps(data, default=str).replace("</", "<\\/")
    return TEMPLATE.read_text().replace("/*__DATA__*/null", payload)
