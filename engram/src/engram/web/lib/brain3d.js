// The live 3D brain (3d-force-graph, vendored). One instance for the whole session: it is the dashboard's ambient
// background and, in the Constellation lens, the thing you explore. Colour is meaning: people and the owner are ink,
// items graphite, beliefs the tier that made them (S2 extraction violet, the owner's own amber). A question lights the
// nodes it touched in the order the pipeline did: considered by search (S0), kept by the judge (S1), cited (S2).
import { api } from "./api.js";
import { reducedMotion, Constellation } from "./ui.js";

const C = {                                    // docs/design.md §2; `born` is a new item arriving (ok)
  ink: "#ECE8DF", person: "#C9C4B8", item: "#6B6860", S0: "#8C96A8", S1: "#46D2E0", S2: "#A393FF", H: "#F3B64A",
  link: "rgba(154,150,137,0.22)", born: "#6FCF97",
};
const HOT = { considered: C.S0, kept: C.S1, cited: C.S2, born: C.born, focus: C.ink };

let G = null, host = null, angle = 0, idle = true, spinning = 0, onPick = null, ready = null;
let why = null, flat = null, flatIndex = new Map();    // no 3D here (why), so a flat 2D map of the same graph instead
let graph = null, retry = 0;                           // the last graph loaded; a timer that tries 3D again
const key = (x) => (typeof x === "object" ? x.id : x);

function color(n) {
  if (n.hot) return HOT[n.hot];
  if (n.type === "owner") return C.ink;
  if (n.type === "person") return C.person;
  if (n.type === "belief") return n.author === "owner" ? C.H : C.S2;
  return C.item;
}

function label(n) {
  const kind = n.type === "belief" ? `${n.kind} · ${n.author === "owner" ? "H you" : "S2 extracted"}` : n.type;
  return `<div class="g-tip"><b>${escapeHtml(n.label || "")}</b><span>${escapeHtml(kind)}${n.date ? " · " + n.date : ""}</span></div>`;
}
function escapeHtml(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }

function webgl() {                              // a probe context, released at once: GPU memory can be scarce
  try {
    const gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl");
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    return !!gl;
  } catch { return false; }
}

/* Why this browser shows the flat map instead of the 3D brain, or null. `?flat` asks for it (a weak projector). */
export function unavailable() { return why; }

export function mount(el) {
  host = el;
  if (G) return;
  why = new URLSearchParams(location.search).has("flat") ? "the flat view was asked for"
    : !window.ForceGraph3D ? "the 3D library did not load" : !webgl() ? "WebGL is turned off in this browser" : null;
  if (why) return;
  if (!try3d()) later(15000);
}

/* Start the 3D brain; on failure undo what it added. A browser short of GPU memory creates a context and loses it at
   once (Safari: getShaderPrecisionFormat is null), so the flat map stands in and 3D is tried again later. */
function try3d() {
  const before = new Set(host.children);
  try { mount3d(host); return true; } catch (e) {
    console.warn("engram: no 3D brain", e);
    G = null; cancelAnimationFrame(spinning);
    for (const c of [...host.children]) if (!before.has(c)) c.remove();
    why = `the 3D view could not start (${e.message})`;
    return false;
  }
}
function later(ms) {
  clearTimeout(retry);
  retry = setTimeout(() => {
    if (G || !host) return;
    if (!try3d()) { later(Math.min(ms * 2, 60000)); return; }
    why = null;
    if (flat) { flat.stop(); flat = null; host.querySelector(".flat-brain")?.remove(); }
    if (graph) G.graphData(graph);
    window.dispatchEvent(new CustomEvent("engram:brain3d"));
  }, ms);
}

function mount3d(el) {
  G = window.ForceGraph3D({ controlType: "orbit" })(el)
    .backgroundColor("#07080B").showNavInfo(false)
    .nodeRelSize(3).nodeResolution(12).nodeOpacity(0.95)
    .nodeVal((n) => (n.type === "owner" ? 14 : n.val || 1) * (n.hot === "cited" || n.hot === "born" ? 3 : n.hot ? 1.8 : 1))
    .nodeColor(color).nodeLabel(label)
    .linkColor((l) => (l.hot ? HOT[l.hot] : C.link)).linkOpacity(0.5)
    .linkWidth((l) => (l.hot ? 1.2 : 0))
    .linkDirectionalParticles((l) => (l.hot && !reducedMotion() ? 2 : 0))
    .linkDirectionalParticleWidth(1.6).linkDirectionalParticleColor((l) => HOT[l.hot] || C.ink)
    .onNodeClick((n) => { idle = false; focus(n.id); onPick && onPick(n); })
    .onBackgroundClick(() => onPick && onPick(null))
    .warmupTicks(reducedMotion() ? 160 : 0).cooldownTicks(reducedMotion() ? 0 : 200);
  G.controls().addEventListener("start", () => { idle = false; });
  G.cameraPosition({ x: 0, y: 40, z: 420 });
  const spin = () => {
    if (G && idle && !reducedMotion()) { angle += 0.0011; G.cameraPosition({ x: 420 * Math.sin(angle), z: 420 * Math.cos(angle) }); }
    spinning = requestAnimationFrame(spin);
  };
  spinning = requestAnimationFrame(spin);
  const size = () => G && G.width(el.clientWidth || innerWidth).height(el.clientHeight || innerHeight);
  new ResizeObserver(size).observe(el);
  size();
}

/* Load (or reload) this brain's graph. Resolves once the data is in. */
export function load() {
  ready = api("/api/graph").then((g) => {
    graph = g;
    try { if (G) G.graphData(g); else if (why && host) flatten(g); } catch (e) { console.warn("engram: graph", e); }
    return g;
  });
  return ready;
}

function flatten(g) {
  if (flat) flat.stop();
  flatIndex = new Map(g.nodes.map((n, i) => [n.id, i]));
  const nodes = g.nodes.map((n, i) => ({ id: i, kind: n.type === "belief" ? n.kind : n.type === "owner" ? "person" : n.type }));
  const links = g.links.map((l) => [flatIndex.get(key(l.source)), flatIndex.get(key(l.target))]).filter(([a, b]) => a != null && b != null);
  const canvas = document.createElement("canvas");
  canvas.className = "flat-brain";
  host.querySelector(".flat-brain")?.remove();
  host.append(canvas);
  flat = Constellation(canvas, { nodes, links }, { seed: "engram" });
  flat.setSpread(0.94, 2.2);
}
const flatMark = (ids) => { if (flat) flat.highlight(ids.map((id) => flatIndex.get(id)).filter((i) => i != null)); };
export function whenReady() { return ready || Promise.resolve(); }

export function clear() {
  if (G) G.graphData({ nodes: [], links: [] });
  if (flat) { flat.stop(); flat = null; host?.querySelector(".flat-brain")?.remove(); }
  ready = null; idle = true; graph = null;
}
export function onSelect(fn) { onPick = fn; }
export function setIdle(v) { idle = v; }
/* Back to the slow orbit around the whole brain: the ambient background behind the other views shows no close-up. */
export function overview() {
  if (!G) return;
  idle = true;
  G.cameraPosition({ x: 420 * Math.sin(angle), y: 40, z: 420 * Math.cos(angle) }, { x: 0, y: 0, z: 0 }, reducedMotion() ? 0 : 800);
}

function restyle() { if (G) G.nodeColor(G.nodeColor()).nodeVal(G.nodeVal()).linkColor(G.linkColor()).linkWidth(G.linkWidth()).linkDirectionalParticles(G.linkDirectionalParticles()); }

/* Merge nodes and links (from /api/node/<id> or an add's result). `hot` marks them, e.g. "born". */
export function merge(g, hot) {
  if (!G || !g) return [];
  const { nodes, links } = G.graphData();
  const have = new Set(nodes.map((n) => n.id));
  const lk = new Set(links.map((l) => key(l.source) + ">" + key(l.target)));
  const add = g.nodes.filter((n) => !have.has(n.id));
  const newLinks = g.links.filter((l) => !lk.has(key(l.source) + ">" + key(l.target)) && (have.has(key(l.source)) || add.some((n) => n.id === key(l.source))) && (have.has(key(l.target)) || add.some((n) => n.id === key(l.target))));
  if (hot) { for (const n of add) n.hot = hot; for (const l of newLinks) l.hot = hot; }
  if (add.length || newLinks.length) G.graphData({ nodes: [...nodes, ...add], links: [...links, ...newLinks] });
  return add;
}

async function ensureItems(ids) {
  const have = new Set(G.graphData().nodes.map((n) => n.id));
  const missing = ids.filter((i) => !have.has(`i:${i}`)).slice(0, 20);
  const got = await Promise.all(missing.map((i) => api(`/api/node/${i}`).catch(() => null)));
  for (const g of got) merge(g);
}

export function clearHot() {
  flatMark([]);
  if (!G) return;
  for (const n of G.graphData().nodes) delete n.hot;
  for (const l of G.graphData().links) delete l.hot;
  restyle();
}

/* A question's path through the brain: considered (S0) → kept (S1) → cited (S2), each after a beat. */
export async function lightQuestion(touched) {
  if (!G) { flatMark([...touched.considered, ...touched.kept, ...touched.cited].map((i) => `i:${i}`)); return; }
  clearHot();
  const all = [...new Set([...touched.considered, ...touched.kept, ...touched.cited])];
  await ensureItems(all);
  const nodes = new Map(G.graphData().nodes.map((n) => [n.id, n]));
  const step = reducedMotion() ? 0 : 650;
  for (const [level, ids] of [["considered", touched.considered], ["kept", touched.kept], ["cited", touched.cited]]) {
    const want = new Set(ids.map((i) => `i:${i}`));
    for (const id of want) if (nodes.has(id)) nodes.get(id).hot = level;
    for (const l of G.graphData().links) if (want.has(key(l.target)) || want.has(key(l.source))) l.hot = level;
    restyle();
    await new Promise((r) => setTimeout(r, step));
  }
  if (touched.cited.length) focus(`i:${touched.cited[0]}`);
}

export function focus(id) {
  if (!G) return false;
  const n = G.graphData().nodes.find((x) => x.id === id);
  if (!n) return false;
  idle = false;
  const r = 1 + 220 / Math.hypot(n.x || 1, n.y || 1, n.z || 1);
  G.cameraPosition({ x: (n.x || 1) * r, y: (n.y || 1) * r, z: (n.z || 1) * r }, n, reducedMotion() ? 0 : 1400);
  return true;
}

export function mark(ids, hot) {
  if (!G) { flatMark(ids); return; }
  const want = new Set(ids);
  for (const n of G.graphData().nodes) if (want.has(n.id)) n.hot = hot;
  restyle();
}

export function node(id) { return G ? G.graphData().nodes.find((x) => x.id === id) : null; }
export function stats() { return G ? { nodes: G.graphData().nodes.length, links: G.graphData().links.length } : { nodes: 0, links: 0 }; }
export { C as colors };
