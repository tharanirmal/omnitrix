"""graphify's build -> cluster -> analyze -> health -> label steps, run on the brain's own graph.

Standalone: executed by graphify's interpreter (`graphify` is a separate uv tool, not a project dependency),
from the directory that holds graphify-out/. The brain is already extracted (Postgres), so graphify's
extraction steps are skipped; `omnitrix brain graphify` writes graphify-out/.graphify_extract.json first.

Communities are named without a model (Step 5): after their best-connected person, organization or project,
else graphify's own hub label - so nothing calls a cloud model.
Writes graph.json, GRAPH_REPORT.md, .graphify_analysis.json and .graphify_labels.json.
"""
import json
from pathlib import Path

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.build import build_from_json
from graphify.cluster import cluster, label_communities_by_hub, score_all
from graphify.diagnostics import diagnose_extraction, format_diagnostic_report
from graphify.export import to_json
from graphify.report import generate

ENTITY_GROUPS = ("project", "organization", "person")
PROJECT_SHARE = 0.6        # a project names its cluster if it has at least 60% of the top entity's links


def name_communities(G, communities: dict[int, list[str]]) -> dict[int, str]:
    """Name each cluster after its best-connected person, organization or project - preferring a project that
    is nearly as connected, since a cluster is usually *about* a project. Clusters without any entity keep
    graphify's hub label."""
    labels = label_communities_by_hub(G, communities)
    for cid, members in communities.items():
        entities = sorted((n for n in members if G.nodes[n].get("brain_group") in ENTITY_GROUPS),
                          key=lambda n: (-G.degree(n), n))
        if not entities:
            continue
        best = entities[0]
        project = next((n for n in entities if G.nodes[n]["brain_group"] == "project"), None)
        if project and G.degree(project) >= PROJECT_SHARE * G.degree(best):
            best = project
        name = G.nodes[best].get("label") or best
        labels[cid] = f"{name} (in-house)" if G.nodes[best].get("brain_self") else name
    return labels


OUT = Path("graphify-out")
ROOT = "."

extraction = json.loads((OUT / ".graphify_extract.json").read_text(encoding="utf-8"))
detection = json.loads((OUT / ".graphify_detect.json").read_text(encoding="utf-8"))

# Step 4 - build, cluster, analyze
G = build_from_json(extraction, root=ROOT, directed=False)
if G.number_of_nodes() == 0:
    raise SystemExit("ERROR: Graph is empty - the brain export produced no nodes.")
communities = cluster(G)
cohesion = score_all(G, communities)
gods = god_nodes(G)
surprises = surprising_connections(G, communities)

# Step 4.5 - health check (read-only)
health = diagnose_extraction(extraction, directed=False, root=ROOT)
print(format_diagnostic_report(health))

# Step 5 - label communities (no model involved)
labels = name_communities(G, communities)
questions = suggest_questions(G, communities, labels)
tokens = {"input": extraction.get("input_tokens", 0), "output": extraction.get("output_tokens", 0)}

# the brain is rebuilt from Postgres every run, so a smaller graph is expected, not a mistake (#479 guard)
to_json(G, communities, str(OUT / "graph.json"), force=True, community_labels=labels)
(OUT / "GRAPH_REPORT.md").write_text(
    generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, ROOT, suggested_questions=questions),
    encoding="utf-8")
(OUT / ".graphify_labels.json").write_text(json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False),
                                           encoding="utf-8")
(OUT / ".graphify_analysis.json").write_text(json.dumps({
    "communities": {str(k): v for k, v in communities.items()},
    "cohesion": {str(k): v for k, v in cohesion.items()},
    "labels": {str(k): v for k, v in labels.items()},
    "gods": gods, "surprises": surprises, "questions": questions,
    "health": {k: v for k, v in health.items() if isinstance(v, (int, float, str))},
}, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")
