// Agent log: every brain recall, newest first, updated live over server-sent events.
// Plain JS, no libraries. Log content (questions, email text) is untrusted, so it only ever goes into textContent.
"use strict";

const $ = (id) => document.getElementById(id);
const els = {
  list: $("list"), detail: $("detail"), more: $("more"), count: $("count"), live: $("live"), clock: $("clock"),
  agent: $("f-agent"), strategy: $("f-strategy"), since: $("f-since"), until: $("f-until"), clear: $("f-clear"),
};
const PAGE = 100;
const state = { entries: [], selected: null, hasMore: false, detailToken: 0 };
const nf = new Intl.NumberFormat("en-IN");

// ----------------------------------------------------------------------------------------- helpers

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style") el.style.cssText = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

function pct(x) {
  if (x == null) return "–";
  if (x > 0 && x < 0.001) return "<0.1%";
  return (x * 100).toFixed(x < 0.1 ? 1 : 0) + "%";
}
const num = (x) => (x == null ? "–" : nf.format(x));
const ms = (x) => (x == null ? "–" : `${Math.round(x)} ms`);
const plural = (n, word) => `${num(n)} ${word}${n === 1 ? "" : "s"}`;

function agentDot(name) {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.codePointAt(0)) >>> 0;
  return `--dot: var(--a${hash % 6})`;
}
const agentChip = (name) => h("span", { class: "agent", style: agentDot(name) }, name);

function filters() {
  return { agent: els.agent.value, strategy: els.strategy.value, since: els.since.value, until: els.until.value };
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

// ------------------------------------------------------------------------------------------- meta

function syncOptions(select, values) {
  const have = new Set([...select.options].map((o) => o.value));
  for (const v of values) if (!have.has(v)) select.append(h("option", { value: v }, v));
}

async function loadMeta() {
  try {
    const meta = await getJSON("/api/meta");
    syncOptions(els.agent, meta.agents);
    syncOptions(els.strategy, meta.strategies);
    els.clock.textContent = `Demo clock ${meta.demo_now_label}${meta.clock_mode === "frozen" ? " (frozen)" : ""}`;
  } catch (err) {
    console.error(err);
  }
}

// ------------------------------------------------------------------------------------------- list

async function loadList({ append = false } = {}) {
  const params = new URLSearchParams({ limit: PAGE });
  for (const [k, v] of Object.entries(filters())) if (v) params.set(k, v);
  if (append && state.entries.length) params.set("before", state.entries[state.entries.length - 1].id);
  try {
    const data = await getJSON(`/api/recalls?${params}`);
    state.entries = append ? state.entries.concat(data.items) : data.items;
    state.hasMore = data.has_more;
    renderList();
  } catch (err) {
    els.list.replaceChildren(h("li", { class: "list-empty" }, `Could not load the log: ${err.message}`));
  }
}

function renderRow(e, fresh = false) {
  const stats = [];
  if (e.returned_chunks != null) stats.push(plural(e.returned_chunks, "chunk"));
  if (e.facts) stats.push(plural(e.facts, "fact"));
  if (e.returned_tokens != null) stats.push(`${num(e.returned_tokens)} tokens`);
  if (e.total_ms != null) stats.push(ms(e.total_ms));
  if (e.share_searched != null) stats.push(`searched ${pct(e.share_searched)}`);
  return h("li", {
      class: `row${e.id === state.selected ? " selected" : ""}${fresh ? " fresh" : ""}`, "data-id": e.id,
      onclick: () => select(e.id),
    },
    h("div", { class: "row-top" },
      h("span", { class: "row-time" }, e.at_label), agentChip(e.agent),
      e.strategy !== "brain" ? h("span", { class: "tag" }, e.strategy) : null),
    h("div", { class: "row-q" }, e.query),
    h("div", { class: "row-stats" }, stats.join(" · ")));
}

function renderList() {
  if (!state.entries.length) {
    const filtered = Object.values(filters()).some(Boolean);
    els.list.replaceChildren(h("li", { class: "list-empty" }, filtered
      ? "No questions match these filters."
      : "No questions yet. Try: uv run omnitrix brain ask \"What is blocking the Mehta quote?\""));
  } else {
    els.list.replaceChildren(...state.entries.map((e) => renderRow(e)));
  }
  els.more.hidden = !state.hasMore;
  renderCount();
}

function matchesQuickFilters(e) {
  const f = filters();
  return (!f.agent || f.agent === e.agent) && (!f.strategy || f.strategy === e.strategy);
}

function onNewEntry(e) {
  syncOptions(els.agent, [e.agent]);
  syncOptions(els.strategy, [e.strategy]);
  loadMeta();                                   // the demo clock may have moved
  if (state.entries.some((x) => x.id === e.id)) return;
  const f = filters();
  if (f.since || f.until) { loadList(); return; }  // time filters are checked by the server
  if (!matchesQuickFilters(e)) return;
  // newest first by demo time; the clock can be moved back, so insert in order rather than always on top
  const t = Date.parse(e.at);
  let i = state.entries.findIndex((x) => Date.parse(x.at) <= t);
  if (i === -1) i = state.entries.length;
  state.entries.splice(i, 0, e);
  const row = renderRow(e, true);
  if (els.list.querySelector(".list-empty")) els.list.replaceChildren();
  els.list.insertBefore(row, els.list.children[i] || null);
  renderCount();
}

function renderCount() {
  const n = state.entries.length;
  els.count.textContent = `${num(n)}${state.hasMore ? "+" : ""} ${n === 1 ? "entry" : "entries"}`;
}

// ----------------------------------------------------------------------------------------- detail

async function select(id, { scroll = false } = {}) {
  state.selected = id;
  for (const row of els.list.children) row.classList.toggle("selected", row.dataset.id === id);
  if (scroll) els.list.querySelector(`[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest" });
  history.replaceState(null, "", `#${id}`);
  document.body.classList.add("show-detail");
  const token = ++state.detailToken;
  try {
    const d = await getJSON(`/api/recalls/${encodeURIComponent(id)}`);
    if (token === state.detailToken) renderDetail(d);
  } catch (err) {
    if (token === state.detailToken) {
      els.detail.replaceChildren(h("div", { class: "empty" }, `Could not load this entry: ${err.message}`));
    }
  }
}

function kpi(label, value, sub) {
  return h("div", { class: "kpi" }, h("div", { class: "kpi-label" }, label), h("div", { class: "kpi-value" }, value),
    h("div", { class: "kpi-sub" }, sub));
}

function section(title, note, ...body) {
  return h("section", { class: "sec" }, h("h3", {}, title, note ? h("small", {}, note) : null), ...body);
}

const SOURCE_LABELS = { demo_id: "demo id", path: "vault", filename: "file" };

function whyChip(reason) {
  const kind = reason.startsWith("meaning") ? "meaning" : reason.startsWith("keyword") ? "keyword"
    : reason.startsWith("names") ? "names" : reason.includes("fallback") ? "fallback" : "other";
  return h("span", { class: kind }, reason);
}

function renderChunk(c) {
  if (c.missing) {
    return h("article", { class: "chunk missing" },
      h("div", { class: "chunk-head" }, h("span", { class: "rank" }, c.rank),
        h("div", { class: "chunk-main" }, h("div", { class: "chunk-title" }, "Chunk no longer in the brain"),
          h("div", { class: "chunk-sub" }, h("code", {}, c.chunk_id), "its document was removed or re-ingested"))),
      h("div", { class: "why" }, c.why.map(whyChip)));
  }
  const text = h("div", { class: "chunk-text" }, c.text);
  const long = c.text.length > 420;
  if (long) text.classList.add("clamp");
  const toggle = long ? h("button", {
    class: "toggle", type: "button",
    onclick: (ev) => {
      const clamped = text.classList.toggle("clamp");
      ev.target.textContent = clamped ? "Show all" : "Show less";
    },
  }, "Show all") : null;
  const href = `/documents/${encodeURIComponent(c.document_id)}?chunk=${encodeURIComponent(c.chunk_id)}`;
  return h("article", { class: "chunk" },
    h("div", { class: "chunk-head" },
      h("span", { class: "rank", title: `score ${c.score}` }, c.rank),
      h("div", { class: "chunk-main" },
        h("div", { class: "chunk-title" }, c.title || "(untitled)"),
        h("div", { class: "chunk-sub" },
          h("span", { class: "tag" }, c.doc_type),
          c.source ? h("span", {}, `${SOURCE_LABELS[c.source.kind] || c.source.kind} `, h("code", {}, c.source.value)) : null,
          c.occurred_at ? h("span", {}, c.occurred_at) : null,
          c.from ? h("span", {}, `from ${c.from}`) : null,
          h("span", {}, `chunk ${c.position + 1} · ${num(c.tokens)} tokens`))),
      h("a", { class: "open", href, target: "_blank", rel: "noopener" }, "Open document ↗")),
    h("div", { class: "why" }, c.why.map(whyChip)),
    text, toggle);
}

const TIMING = [
  ["entities_ms", "find names", "var(--names)"], ["scope_ms", "scope", "var(--a5)"],
  ["embed_ms", "embed question", "var(--a2)"], ["vector_ms", "meaning search", "var(--meaning)"],
  ["keyword_ms", "keyword search", "var(--keyword)"], ["facts_ms", "facts", "var(--a4)"],
];

function renderTiming(cost) {
  const parts = TIMING.filter(([k]) => cost.timings[k] != null);
  const total = cost.total_ms || parts.reduce((s, [k]) => s + cost.timings[k], 0) || 1;
  const other = Math.max(0, total - parts.reduce((s, [k]) => s + cost.timings[k], 0));
  return [
    h("div", { class: "timing", role: "img", "aria-label": `Time taken: ${ms(cost.total_ms)}` },
      parts.map(([k, label, color]) => h("span", {
        style: `width:${(100 * cost.timings[k]) / total}%;background:${color}`, title: `${label}: ${ms(cost.timings[k])}`,
      })),
      other > 0.5 ? h("span", { style: `width:${(100 * other) / total}%;background:var(--line-strong)`,
        title: `ranking, counting, other: ${ms(other)}` }) : null),
    h("div", { class: "legend" },
      parts.map(([k, label, color]) => h("span", {}, h("i", { style: `background:${color}` }), `${label} ${ms(cost.timings[k])}`)),
      other > 0.5 ? h("span", {}, h("i", { style: "background:var(--line-strong)" }), `other ${ms(other)}`) : null),
  ];
}

function renderDetail(d) {
  const s = d.search;
  const c = d.cost;
  const entities = d.entities.length
    ? h("div", { class: "chips" }, d.entities.map((e) => h("span", { class: "ent" }, e.name, h("small", {}, e.type))))
    : h("p", { class: "note" }, "No known people, organisations or projects in the question, so it searched everything.");
  const widened = d.scope_entities.length
    ? h("div", { class: "chips", style: "margin-top:8px" }, h("span", { class: "note" }, "Scope widened to"),
      d.scope_entities.map((e) => h("span", { class: "ent scope" }, e.name, h("small", {}, e.type))))
    : null;

  const searched = [
    h("div", { class: "bar", role: "img", "aria-label": `Searched ${pct(s.share_documents)} of documents` },
      h("span", { style: `width:${Math.max(0, Math.min(100, (s.share_documents ?? 1) * 100))}%` })),
    h("div", { class: "bar-caption" },
      `${num(s.scope_documents)} of ${num(s.corpus_documents)} documents (${pct(s.share_documents)})`,
      s.scope_chunks != null ? ` · ${num(s.scope_chunks)} of ${num(s.corpus_chunks)} chunks (${pct(s.share_chunks)})` : "",
      s.candidates != null ? ` · ${num(s.candidates)} candidates ranked` : ""),
    !s.scoped && d.strategy === "brain" && d.entities.length
      ? h("p", { class: "note warn" }, "The scope covered most of the brain, so it searched everything.") : null,
    s.fallback ? h("p", { class: "note warn" }, "Nothing matched inside the scope - it fell back to searching everything.") : null,
  ];

  els.detail.replaceChildren(h("div", { class: "detail" },
    h("button", { class: "btn back", type: "button", onclick: () => document.body.classList.remove("show-detail") }, "← All entries"),
    h("div", { class: "d-meta" }, agentChip(d.agent), h("span", { class: "tag" }, d.strategy), h("span", {}, d.at_label),
      h("code", {}, d.id)),
    h("h2", {}, d.query),
    h("div", { class: "kpis" },
      kpi("Searched", pct(s.share_documents), `${num(s.scope_documents)} of ${num(s.corpus_documents)} documents`),
      kpi("Returned", `${d.chunks.length} + ${d.facts.length}`, "chunks + facts"),
      kpi("Tokens", num(c.returned_tokens), c.corpus_tokens ? `${pct(c.share_returned)} of ${num(c.corpus_tokens)} in the brain` : ""),
      kpi("Time", ms(c.total_ms), c.timings.embed_ms != null ? `${ms(c.timings.embed_ms)} embedding` : "")),
    section("Entities recognised", null, entities, widened),
    section("How much was searched", null, ...searched),
    section("Returned chunks", `${d.chunks.length}, in the order the agent sees them`,
      d.chunks.length ? d.chunks.map(renderChunk) : h("p", { class: "note" }, "No chunks returned.")),
    section("Facts added", d.facts.length ? `${d.facts.length}` : null,
      d.facts.length
        ? h("ul", { class: "facts" }, d.facts.map((f) => h("li", {}, h("span", {}, f.text), h("code", {}, f.ref))))
        : h("p", { class: "note" }, "No facts added.")),
    section("Time taken", ms(c.total_ms), ...renderTiming(c))));
  els.detail.scrollTop = 0;
}

// ------------------------------------------------------------------------------------------- live

function connect() {
  let opened = false;
  const es = new EventSource("/api/recalls/stream");
  es.onopen = () => {
    els.live.className = "live on";
    els.live.textContent = "live";
    if (opened) loadList();            // reconnected: pick up anything missed while offline
    opened = true;
  };
  es.onerror = () => {
    els.live.className = "live off";
    els.live.textContent = "reconnecting";
  };
  es.addEventListener("recall", (ev) => onNewEntry(JSON.parse(ev.data)));
}

// ---------------------------------------------------------------------------------------- wiring

for (const el of [els.agent, els.strategy, els.since, els.until]) el.addEventListener("change", () => loadList());
els.clear.addEventListener("click", () => {
  els.agent.value = els.strategy.value = els.since.value = els.until.value = "";
  loadList();
});
els.more.addEventListener("click", () => loadList({ append: true }));
els.list.addEventListener("keydown", (ev) => {
  if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
  ev.preventDefault();
  const i = state.entries.findIndex((e) => e.id === state.selected);
  const next = state.entries[Math.max(0, Math.min(state.entries.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)))];
  if (next) select(next.id, { scroll: true });
});

(async () => {
  await Promise.all([loadMeta(), loadList()]);
  const wanted = location.hash.slice(1);
  if (wanted) select(wanted, { scroll: true });
  else if (state.entries.length && window.matchMedia("(min-width: 821px)").matches) select(state.entries[0].id);
  connect();
})();
