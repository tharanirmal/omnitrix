// Database, three lenses: the Constellation (the live 3D brain: ask it, search it, click a node for its provenance),
// the Schema atlas (tables sized by rows, foreign keys, a sample of rows, and the read-only SQL console), and the
// Belief timeline (valid time × recorded time; superseded beliefs fade into their replacements).
import * as ui from "../lib/ui.js";
import { api, every } from "../lib/api.js";
import * as brain from "../lib/brain3d.js";

const LENSES = [
  { value: "constellation", label: "Constellation", icon: "constellation" },
  { value: "atlas", label: "Schema atlas", icon: "table" },
  { value: "timeline", label: "Belief timeline", icon: "timeline" },
];

export function mount(root, ctx) {
  let lens = null, current = null;
  const body = ui.h("div", { class: "lens", style: { viewTransitionName: "lens" } });
  const seg = ui.Segmented({ label: "Database lens", options: LENSES, value: pick(ctx.sub), onChange: (v) => { location.hash = `#/database/${v}`; } });
  root.append(ui.h("section", { class: "view database-view" },
    ui.h("header", { class: "view-head compact" }, seg), body));

  function pick(sub) { return LENSES.some((l) => l.value === sub) ? sub : "constellation"; }
  function show(sub, params) {
    const next = pick(sub);
    document.body.dataset.lens = next;
    seg.select(next);
    if (next === lens && current && current.route) { current.route(params); return; }
    if (current) current.unmount();
    body.textContent = "";
    lens = next;
    current = { constellation, atlas, timeline }[next](body, params, ctx);
  }
  show(ctx.sub, ctx.params);
  return {
    route: (sub, params) => show(sub, params),
    unmount: () => { if (current) current.unmount(); delete document.body.dataset.lens; brain.onSelect(null); },
  };
}

/* ---------------------------------------------------------------------------------------------- Constellation */
function constellation(host, params, ctx) {
  const out = ui.h("div", { class: "ask-out", "aria-live": "polite" });
  const input = ui.h("input", { class: "eg-input", type: "text", placeholder: "Ask your brain…", "aria-label": "Question", autocomplete: "off" });
  let mode = "ask";
  const modeSeg = ui.Segmented({ label: "Ask or search", options: [{ value: "ask", label: "Ask" }, { value: "search", label: "Search" }], onChange: (v) => {
    mode = v; go.querySelector("span").textContent = v === "ask" ? "Ask" : "Search"; input.placeholder = v === "ask" ? "Ask your brain…" : "Keywords or meaning…"; input.setAttribute("aria-label", v === "ask" ? "Question" : "Search"); } });
  const go = ui.Button({ label: "Ask", type: "submit" });
  const form = ui.h("form", { class: "ask-form" }, input, go);
  const examples = ui.h("div", { class: "examples" },
    ...["Where and at what time did Vince suggest meeting Michael Garberding on Tuesday?", "Who was Bernard Murphy's PhD supervisor?"]
      .map((q) => ui.h("button", { type: "button", text: q, onClick: () => { input.value = q; form.requestSubmit(); } })));
  const flatNote = brain.unavailable() ? ui.h("p", { class: "hint", text: `A flat map of the brain: ${brain.unavailable()}. The 3D view comes back by itself when the browser allows it.` }) : null;
  const back3d = () => flatNote?.remove();
  window.addEventListener("engram:brain3d", back3d);
  const panel = ui.h("section", { class: "overlay ask-panel eg-ontile", "aria-label": "Ask or search" },
    ui.h("div", { class: "ask-top" }, modeSeg), form, examples, out, flatNote);
  const detail = ui.h("aside", { class: "overlay detail-panel eg-ontile", hidden: true, "aria-label": "Selected node", "aria-live": "polite" });
  const legend = ui.h("div", { class: "overlay legend", "aria-hidden": "true" },
    ...[["ink", "people"], ["item", "items"], ["S2", "beliefs · S2"], ["H", "yours · H"]].map(([c, t]) => ui.h("span", null, ui.h("i", { style: { background: brain.colors[c] } }), t)),
    ui.h("span", { class: "sep" }), ...[["S0", "considered"], ["S1", "kept"], ["S2", "cited"]].map(([c, t]) => ui.h("span", null, ui.h("i", { class: "ring", style: { borderColor: brain.colors[c] } }), t)));
  host.append(panel, detail, legend);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    go.disabled = true;
    out.textContent = "";
    detail.hidden = true;                                  // the last answer's source no longer applies
    if (mode === "search") {
      try {
        const hits = await api(`/api/search?q=${encodeURIComponent(q)}&k=10`);
        out.append(ui.h("p", { class: "eg-caps", text: `${hits.length} hits · keyword + meaning` }),
          ui.h("ol", { class: "hits" }, ...hits.map((h) => ui.h("li", null, ui.h("button", { type: "button", onClick: () => openItem(h.item) },
            ui.h("b", { text: h.subject || "(no subject)" }), ui.h("span", { class: "meta eg-mono", text: `${h.date || ""} · ${h.from} · ${[].concat(h.why).join(", ")}` }), ui.h("span", { class: "snip", text: h.text.slice(0, 200) }))))));
        brain.clearHot();
        brain.mark(hits.map((h) => `i:${h.item}`), "considered");
      } catch (ex) { out.append(ui.h("p", { class: "error", role: "alert", text: ex.message })); }
      go.disabled = false;
      return;
    }
    const t0 = performance.now();
    const clock = ui.h("span", { class: "eg-mono" });
    const tick = setInterval(() => { clock.textContent = `${((performance.now() - t0) / 1000).toFixed(1)} s`; }, 100);
    out.append(ui.h("p", { class: "thinking" }, ui.TierChip({ tier: "S0", live: true, onTile: true, label: "search" }), " → ", ui.TierChip({ tier: "S1", live: true, onTile: true, label: "judge" }), " → ", ui.TierChip({ tier: "S2", live: true, onTile: true, label: "answer" }), " ", clock));
    try {
      const r = await api("/api/ask", { question: q });
      clearInterval(tick);
      out.textContent = "";
      const v = r.verdict;
      out.append(
        ui.h("p", { class: "answer", text: r.answer }),
        ui.h("p", { class: "verdict" },
          ui.TierChip({ tier: "S2", onTile: true, label: `answered by ${r.answered_by || "S2"}` }), " ",
          v ? ui.TierChip({ tier: "S1", onTile: true, label: `${v.value === "yes" ? "supported" : "not supported"} · p ${v.p.toFixed(2)}` }) : ui.h("span", { class: "hint", text: "not checked" }),
          ui.h("span", { class: "eg-mono hint", text: ` ${r.considered} considered · ${r.kept} kept · ${r.seconds} s` })),
        ui.h("ol", { class: "hits cites" }, ...r.cites.map((c) => ui.h("li", null, ui.h("button", { type: "button", onClick: () => openItem(c.item) },
          ui.h("b", { text: c.subject || "(no subject)" }), ui.h("span", { class: "meta eg-mono", text: `item:${c.item} · ${c.date || ""} · ${c.from}` }))))));
      brain.lightQuestion(r.touched);
    } catch (ex) {
      clearInterval(tick);
      out.textContent = "";
      out.append(ui.h("p", { class: "error", role: "alert", text: ex.message }));
    }
    go.disabled = false;
  });

  async function openItem(id) {
    detail.hidden = false;
    detail.replaceChildren(ui.h("p", { class: "hint", text: "Reading…" }));
    try {
      const it = await api(`/api/item/${id}`);
      if (!brain.focus(`i:${id}`)) { brain.merge(await api(`/api/node/${id}`), "focus"); setTimeout(() => brain.focus(`i:${id}`), 600); }
      detail.replaceChildren(closeBtn(),
        ui.h("p", { class: "eg-caps", text: `item:${it.id} · ${it.kind} · ${it.sent_at || ""}` }),
        ui.h("h3", { class: "tagline", text: it.subject || "(no subject)" }),
        ui.h("p", { class: "meta eg-mono", text: `${it.from_addr} → ${(it.to_addrs || []).slice(0, 3).join(", ")}` }),
        ui.h("pre", { class: "body", text: (it.body || "").slice(0, 2400) }));
    } catch (e) { detail.replaceChildren(closeBtn(), ui.h("p", { class: "error", text: e.message })); }
  }
  async function openBelief(id) {
    detail.hidden = false;
    detail.replaceChildren(ui.h("p", { class: "hint", text: "Reading…" }));
    try {
      const b = await api(`/api/belief/${id}`);
      brain.focus(`b:${id}`);
      detail.replaceChildren(closeBtn(),
        ui.h("p", { class: "eg-caps", text: `${b.kind} · ${b.current ? "current" : "superseded"} · ${b.status}${b.trust ? " · trust " + b.trust : ""}` }),
        ui.h("h3", { class: "tagline", text: b.statement }),
        ui.h("p", { class: "verdict" }, ui.TierChip({ tier: b.tier, onTile: true, label: b.tier === "H" ? "H · written by you" : "S2 · extracted" }), " ",
          ui.h("span", { class: "eg-mono", text: `p ${Number(b.confidence).toFixed(2)}` })),
        ui.h("blockquote", { class: "quote", text: b.quote }),
        ui.h("dl", { class: "facts" },
          ui.h("dt", { class: "eg-caps", text: "who" }), ui.h("dd", { text: [b.actor, b.other].filter(Boolean).join(" → ") }),
          ui.h("dt", { class: "eg-caps", text: "valid from" }), ui.h("dd", { class: "eg-mono", text: b.valid_from || "—" }),
          ui.h("dt", { class: "eg-caps", text: "recorded" }), ui.h("dd", { class: "eg-mono", text: b.recorded || "—" }),
          b.due_at ? ui.h("dt", { class: "eg-caps", text: "due" }) : null, b.due_at ? ui.h("dd", { class: "eg-mono", text: b.due_at }) : null),
        ui.h("p", { class: "eg-caps", text: "source" }),
        ui.h("button", { type: "button", class: "source", onClick: () => openItem(b.item.id) }, ui.h("b", { text: b.item.subject || "(no subject)" }), ui.h("span", { class: "meta eg-mono", text: `item:${b.item.id} · ${b.item.date || ""} · ${b.item.from}` })),
        b.gate.length ? ui.h("p", { class: "eg-caps", text: "the gate's judgements" }) : null,
        ...b.gate.map((g) => ui.h("p", { class: "gate-row" }, ui.TierChip({ tier: g.tier, onTile: true }), ui.h("span", { class: "eg-mono", text: ` ${g.model} · ${g.value} · P(yes) ${g.p.toFixed(2)}` }))));
    } catch (e) { detail.replaceChildren(closeBtn(), ui.h("p", { class: "error", text: e.message })); }
  }
  function closeBtn() { return ui.Button({ variant: "icon", icon: "x", ariaLabel: "Close", className: "close", onClick: () => { detail.hidden = true; } }); }

  brain.onSelect((n) => {
    if (!n) return;
    if (n.type === "item") openItem(n.item);
    else if (n.type === "belief") openBelief(n.belief);
    else if (n.type === "person") {
      detail.hidden = false;
      detail.replaceChildren(closeBtn(), ui.h("p", { class: "eg-caps", text: "person" }), ui.h("h3", { class: "tagline", text: n.label }),
        ui.h("p", { class: "meta eg-mono", text: n.addr || "" }),
        ui.Button({ label: "Their beliefs on the timeline", variant: "secondary", className: "on-tile", onClick: () => { location.hash = `#/database/timeline?person=${encodeURIComponent(n.label)}`; } }));
    }
  });
  const route = (p) => { if (p.get("item")) openItem(Number(p.get("item"))); if (p.get("belief")) openBelief(Number(p.get("belief"))); };
  route(params);
  brain.setIdle(true);
  return { route, unmount: () => { brain.clearHot(); brain.overview(); window.removeEventListener("engram:brain3d", back3d); } };
}

/* ---------------------------------------------------------------------------------------------- Schema atlas */
function layout(tables, fks) {
  // a small deterministic force layout: tables repel, keys pull, everything stays in the unit square
  const n = tables.length, pos = tables.map((t, i) => ({ x: 0.5 + 0.35 * Math.cos(i / n * 6.283), y: 0.5 + 0.35 * Math.sin(i / n * 6.283) }));
  const idx = new Map(tables.map((t, i) => [t.name, i]));
  const edges = fks.map(([a, b]) => [idx.get(a), idx.get(b)]).filter(([a, b]) => a != null && b != null && a !== b);
  for (let it = 0; it < 300; it++) {
    const f = pos.map(() => ({ x: 0, y: 0 }));
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const dx = pos[i].x - pos[j].x, dy = pos[i].y - pos[j].y, d2 = dx * dx + dy * dy + 1e-4, k = 0.0018 / d2;
      f[i].x += dx * k; f[i].y += dy * k; f[j].x -= dx * k; f[j].y -= dy * k;
    }
    for (const [a, b] of edges) {
      const dx = pos[b].x - pos[a].x, dy = pos[b].y - pos[a].y;
      f[a].x += dx * 0.02; f[a].y += dy * 0.02; f[b].x -= dx * 0.02; f[b].y -= dy * 0.02;
    }
    for (let i = 0; i < n; i++) {
      f[i].x += (0.5 - pos[i].x) * 0.004; f[i].y += (0.5 - pos[i].y) * 0.004;
      pos[i].x = Math.min(0.94, Math.max(0.06, pos[i].x + Math.max(-0.03, Math.min(0.03, f[i].x))));
      pos[i].y = Math.min(0.9, Math.max(0.08, pos[i].y + Math.max(-0.03, Math.min(0.03, f[i].y))));
    }
  }
  return pos;
}

function atlas(host, params, ctx) {
  const slot = ui.h("div", { class: "atlas-slot" }, ui.h("p", { class: "loading", text: "Reading the schema…" }));
  const sqlBox = sqlConsole();
  host.append(slot, sqlBox);
  let at = null, stop = () => {};
  api("/api/schema").then((sc) => {
    const tables = sc.tables.filter((t) => t.name !== "schema_migrations");
    const pos = layout(tables, sc.fks);
    tables.forEach((t, i) => { t.x = pos[i].x; t.y = pos[i].y; t.view = t.kind !== "table"; });
    const wide = host.clientWidth > 720;
    at = ui.SchemaAtlas({ tables, fks: sc.fks.map(([a, b]) => [a, b]), width: wide ? 760 : 420, height: wide ? 460 : 520, onSelect: (t) => sample(t) });
    slot.replaceChildren(at);
    at.side.replaceChildren(ui.h("span", { class: "eg-caps", text: `${tables.filter((t) => !t.view).length} tables · ${tables.filter((t) => t.view).length} views · ${sc.fks.length} keys` }),
      ui.h("p", { class: "hint", text: "Select a table for its columns and a sample of rows, read through the read-only role." }));
    stop = every(8000, async () => {
      const s2 = await api("/api/schema");
      for (const t of s2.tables) { const old = tables.find((x) => x.name === t.name); if (old && t.rows !== old.rows && t.rows != null) { old.rows = t.rows; at.setCount(t.name, t.rows); } }
    });
  }).catch((e) => slot.replaceChildren(ui.h("p", { class: "error", text: e.message })));

  async function sample(t) {
    const side = at.side;
    side.querySelector(".sample")?.remove();
    const box = ui.h("div", { class: "sample" }, ui.h("p", { class: "hint", text: "Sampling…" }));
    side.append(box);
    try {
      const r = await api(`/api/schema/${encodeURIComponent(t.name)}`);
      box.replaceChildren(ui.h("p", { class: "eg-caps", text: `sample · ${r.sample.rows.length} rows` }), table(r.sample.columns, r.sample.rows, true));
    } catch (e) { box.replaceChildren(ui.h("p", { class: "error", text: e.message })); }
  }
  return { unmount: () => stop() };
}

function table(columns, rows, compact) {
  return ui.h("div", { class: "grid-scroll" + (compact ? " compact" : "") }, ui.h("table", { class: "grid" },
    ui.h("thead", null, ui.h("tr", null, ...columns.map((c) => ui.h("th", { scope: "col", text: c })))),
    ui.h("tbody", null, ...rows.map((r) => ui.h("tr", null, ...r.map((v) => ui.h("td", { class: typeof v === "number" ? "num" : null, text: v == null ? "∅" : String(v) })))))));
}

function sqlConsole() {
  const ta = ui.h("textarea", { class: "eg-input sql", rows: "4", spellcheck: "false", "aria-label": "SQL (read-only)" });
  ta.value = "SELECT kind, count(*) AS beliefs, round(avg(confidence)::numeric, 2) AS mean_p\nFROM current_beliefs GROUP BY kind ORDER BY beliefs DESC";
  const res = ui.h("div", { class: "sql-out", "aria-live": "polite" });
  const run = async () => {
    res.replaceChildren(ui.h("p", { class: "hint", text: "Running…" }));
    try {
      const r = await api("/api/sql", { sql: ta.value });
      res.replaceChildren(ui.h("p", { class: "eg-caps" }, `${r.rows.length} rows · `, ui.h("span", { class: "eg-mono", text: `${r.ms} ms` }), r.rows.length === 500 ? " · first 500" : ""), table(r.columns, r.rows));
    } catch (e) { res.replaceChildren(ui.h("p", { class: "error", role: "alert", text: e.message })); }
  };
  ta.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); run(); } });
  return ui.h("details", { class: "sql-console" },
    ui.h("summary", null, ui.h("span", { class: "eg-caps", text: "advanced" }), " Read-only SQL console"),
    ui.h("p", { class: "hint", text: "One statement, a read-only role and transaction, 3 s, at most 500 rows. ⌘↵ runs it." }),
    ta, ui.h("div", { class: "row" }, ui.Button({ label: "Run", variant: "utility", onClick: run })), res);
}

/* ---------------------------------------------------------------------------------------------- Belief timeline */
function timeline(host, params) {
  const slot = ui.h("div", { class: "timeline-slot" }, ui.h("p", { class: "loading", text: "Reading beliefs…" }));
  host.append(slot);
  const load = (p) => {
    const person = p.get("person");
    const q = person ? `?person=${encodeURIComponent(person)}` : "";
    api(`/api/timeline${q}`).then((r) => {
      if (!r.beliefs.length) { slot.replaceChildren(ui.h("p", { class: "empty", text: person ? `No beliefs about ${person} yet.` : "No beliefs yet. Add data, and the memory builder distils commitments, decisions and meetings here." })); return; }
      const beliefs = r.beliefs.slice(0, 80).map((b) => ({ ...b, valid: [b.valid[0], b.valid[1]], recorded: [b.recorded[0], b.recorded[1]] }));
      const people = [...new Set([...(person ? [person] : []), ...r.people])].slice(0, 6);
      const wide = host.clientWidth > 720;
      const tl = ui.BeliefTimeline({ beliefs, people, width: wide ? 1100 : Math.max(340, host.clientWidth - 48), height: wide ? 440 : 520 });
      slot.replaceChildren(tl, ui.h("p", { class: "hint", text: `${r.beliefs.length} beliefs${r.beliefs.length > 80 ? " (the latest 80 shown)" : ""}. Across: when a belief holds in the world. Down: when the brain held it. Dashed: superseded.` }));
      if (person) tl.querySelectorAll(".eg-tl-filters button").forEach((b) => { if (b.textContent === person) b.click(); });
    }).catch((e) => slot.replaceChildren(ui.h("p", { class: "error", text: e.message })));
  };
  load(params);
  return { route: load, unmount: () => {} };
}
