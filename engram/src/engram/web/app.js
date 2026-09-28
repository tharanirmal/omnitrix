// engram's page: sign in to a brain, then a persistent shell (top bar, sub-nav, ⌘K) around four views, with the live
// 3D brain behind everything. Pollers publish what changes (counts, approvals, new ledger rows) on a small event bus;
// views subscribe while they are mounted. No build step: plain ES modules served by `engram serve`.
import * as ui from "./lib/ui.js";
import { api, emit, every, on } from "./lib/api.js";
import * as brain from "./lib/brain3d.js";
import * as login from "./views/login.js";
import * as agentsView from "./views/agents.js";
import * as databaseView from "./views/database.js";
import * as addView from "./views/add.js";
import * as auditView from "./views/audit.js";
import { approvalCard } from "./views/approvals.js";

const VIEWS = {
  agents: { title: "Agents", icon: "agents", mod: agentsView },
  database: { title: "Database", icon: "database", mod: databaseView },
  add: { title: "Add data", icon: "add", mod: addView },
  audit: { title: "Audit", icon: "ledger", mod: auditView },
};
const $app = document.getElementById("app");
const $stage = document.getElementById("stage");
const state = { profile: null, current: null, name: null, stops: [], topbar: null, palette: null, agents: [], pending: [] };

export function announce(text) { const a = document.getElementById("announce"); a.textContent = ""; setTimeout(() => { a.textContent = text; }, 30); }

/* ------------------------------------------------------------------------------------------------ theme */
function theme(next) {
  let t = next;
  if (!t) { try { t = localStorage.getItem("engram-theme"); } catch { t = null; } }
  t = t === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = t;
  if (next) { try { localStorage.setItem("engram-theme", t); } catch { /* private window */ } }
  return t;
}

/* ------------------------------------------------------------------------------------------------ boot */
async function boot() {
  theme();
  on("signed-out", () => { if (state.profile) showLogin(); });
  let session = null;
  try { session = (await api("/api/session")).profile; } catch { /* server down: the login page says so */ }
  if (session) startDashboard(session);
  else showLogin();
}

function stopAll() {
  state.stops.forEach((s) => s());
  state.stops = [];
  if (state.current && state.current.unmount) state.current.unmount();
  state.current = null;
  state.name = null;
  if (state.palette && state.palette.isConnected) state.palette.close();
}

async function showLogin(opts = {}) {
  stopAll();
  state.profile = null;
  document.body.dataset.mode = "login";
  delete document.body.dataset.view;
  brain.clear();
  $app.textContent = "";
  await login.mount($app, {
    collapseFrom: opts.collapseFrom,
    onUnlocked: async (profile, tile) => {
      const ghost = await tile.expand($stage);          // the tile's constellation grows into the whole screen
      startDashboard(profile, { ghost });
    },
  });
}

/* ------------------------------------------------------------------------------------------------ the shell */
function startDashboard(profile, opts = {}) {
  stopAll();
  login.unmount();
  state.profile = profile;
  state.s1 = state.s2 = null;                           // a new top bar: show the models from the first status
  document.body.dataset.mode = "dashboard";
  $app.textContent = "";

  const top = ui.TopBar({ brain: profile.name, color: `var(--tier-${profile.color || "s1"})`, counts: {}, pending: 0,
    onPending: toggleApprovals, onCommand: () => openPalette() });
  state.topbar = top;
  const nav = ui.h("nav", { class: "subnav-links", "aria-label": "Views" });
  for (const [name, v] of Object.entries(VIEWS)) {
    nav.append(ui.h("a", { href: `#/${name}`, "data-view": name }, ui.Icon(v.icon, { size: "sm" }), ui.h("span", { text: v.title })));
  }
  const title = ui.h("h1", { class: "subnav-title" });
  const tools = ui.h("div", { class: "subnav-tools" },
    ui.Button({ variant: "pearl", icon: "pulse", ariaLabel: "Switch light or dark theme", className: "theme-btn", onClick: () => { const t = theme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"); announce(`${t} theme`); } }),
    ui.Button({ variant: "pearl", label: "Sign out", onClick: signOut }));
  const sub = ui.h("div", { class: "subnav" }, title, nav, tools);
  const approvals = ui.h("section", { class: "approvals-pop eg-ontile", id: "approvals", hidden: true, "aria-label": "Waiting on you" });
  const main = ui.h("main", { id: "view", class: "view-host", tabindex: "-1" });
  $app.append(top, sub, approvals, main);

  // the 3D brain is the backdrop, never a gate: if WebGL is unavailable or the graph fails, the page works without it
  try { brain.mount($stage); } catch (e) { console.warn("engram: no 3D brain", e); }
  brain.load().catch(() => {});
  if (opts.ghost) {
    const settled = Promise.race([brain.whenReady().catch(() => {}), ui.wait(4000)]);
    settled.then(() => ui.wait(ui.reducedMotion() ? 0 : 450)).then(() => {
      const g = opts.ghost.ghost;
      const gone = () => { opts.ghost.constellation.stop(); g.remove(); };
      ui.settle(ui.anim(g, [{ opacity: 1 }, { opacity: 0 }], { duration: ui.reducedMotion() ? 120 : 500, fill: "forwards" }), 1100).then(gone);
    });
  }

  // pollers: counts, approvals (long-poll), new ledger rows
  state.stops.push(every(3000, async () => {
    const s = await api("/api/status");
    top.setCounts({ items: s.items, beliefs: s.beliefs, judgements: s.judgements });
    if (s.s1 !== state.s1 || s.s2 !== state.s2) { state.s1 = s.s1; state.s2 = s.s2; top.setModels(s.s1, s.s2); }
    emit("status", s);
  }));
  state.stops.push(pendingLoop());
  state.stops.push(ledgerLoop());
  state.stops.push(on("pending", renderApprovalsPop));
  const keys = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openPalette(); }
    if (e.key === "Escape" && !approvals.hidden) { approvals.hidden = true; document.querySelector(".eg-pending")?.focus(); }
  };
  document.addEventListener("keydown", keys);
  state.stops.push(() => document.removeEventListener("keydown", keys));
  const hc = () => route();
  addEventListener("hashchange", hc);
  state.stops.push(() => removeEventListener("hashchange", hc));
  if (!location.hash || location.hash === "#") history.replaceState(null, "", "#/database/constellation");
  route(true);
}

function parseHash() {
  const [path, query] = location.hash.replace(/^#\/?/, "").split("?");
  const [name, sub] = path.split("/");
  return { name: VIEWS[name] ? name : "database", sub: sub || null, params: new URLSearchParams(query || "") };
}

function route(first) {
  const { name, sub, params } = parseHash();
  const swap = () => {
    document.querySelectorAll(".subnav-links a").forEach((a) => a.setAttribute("aria-current", a.dataset.view === name ? "page" : "false"));
    document.querySelector(".subnav-title").textContent = VIEWS[name].title;
    document.body.dataset.view = name;
    if (state.name === name && state.current && state.current.route) { state.current.route(sub, params); return; }
    if (state.current && state.current.unmount) state.current.unmount();
    const host = document.getElementById("view");
    host.textContent = "";
    state.name = name;
    state.current = VIEWS[name].mod.mount(host, { sub, params, profile: state.profile, pending: () => state.pending, announce });
    document.title = `${VIEWS[name].title} · ${state.profile.name} · engram`;
  };
  if (!first && state.name !== name) ui.transition(swap);
  else swap();
}

export function go(hash) { if (location.hash === hash) route(); else location.hash = hash; }

async function signOut() {
  const name = state.profile && state.profile.name;
  stopAll();                                             // no poll may run into the ended session
  try { await api("/api/logout", {}); } catch { /* the session is gone either way */ }
  showLogin({ collapseFrom: name });
}

/* ------------------------------------------------------------------------------------------------ pollers */
function pendingLoop() {
  let stopped = false, version = null;
  const ctl = new AbortController();
  (async () => {
    while (!stopped) {
      try {
        const q = version === null ? "" : `?since=${version}&wait=20`;
        const r = await api(`/api/pending${q}`, undefined, { signal: ctl.signal });
        version = r.version;
        state.pending = r.pending;
        state.topbar.setPending(r.pending.length);
        emit("pending", r.pending);
      } catch (e) {
        if (stopped || e.status === 401) return;
        await ui.wait(3000);
      }
    }
  })();
  return () => { stopped = true; ctl.abort(); };
}

function ledgerLoop() {
  let last = null;
  return every(1500, async () => {
    if (last === null) {
      const r = await api("/api/ledger?limit=60");
      last = r.last_id || 0;
      emit("ledger-history", r.rows.slice().reverse());
      return;
    }
    const r = await api(`/api/ledger?after_id=${last}&limit=100`);
    if (!r.rows.length) return;
    const rows = r.rows.slice().reverse();                 // oldest first, the order they happened
    last = rows[rows.length - 1].id;
    for (const row of rows) {
      const m = /^act:([0-9a-f]+)$/.exec(row.subject);
      if (row.tier === "H" && m) emit("decided", { run: m[1], approved: row.value === "yes", channel: row.model.startsWith("owner:watch") ? "watch" : "page", device: row.model.split(":")[2] || "" });
    }
    emit("ledger", rows);
  });
}

/* ------------------------------------------------------------------------------------------------ approvals */
function toggleApprovals() {
  const pop = document.getElementById("approvals");
  pop.hidden = !pop.hidden;
  if (!pop.hidden) { renderApprovalsPop(state.pending); (pop.querySelector("button") || pop).focus(); }
}

const popCards = new Map();
function renderApprovalsPop(list) {
  const pop = document.getElementById("approvals");
  if (!pop) return;
  if (!list.length && !popCards.size) {
    pop.textContent = "";
    pop.append(ui.h("p", { class: "empty", text: "Nothing is waiting on you. When the gate sends an action here, it appears in this card and on your watch." }));
    return;
  }
  pop.querySelector(".empty")?.remove();
  for (const p of list) {
    if (popCards.has(p.run)) continue;
    const card = approvalCard(p, () => { popCards.delete(p.run); if (!state.pending.length) setTimeout(() => { pop.hidden = true; }, 1600); });
    popCards.set(p.run, card);
    pop.append(card);
  }
}

/* ------------------------------------------------------------------------------------------------ ⌘K */
function staticCommands() {
  const cmds = [
    { group: "Views", title: "Agents · switchboard", icon: "agents", run: () => go("#/agents") },
    { group: "Views", title: "Database · constellation", icon: "constellation", run: () => go("#/database/constellation") },
    { group: "Views", title: "Database · schema atlas", icon: "table", run: () => go("#/database/atlas") },
    { group: "Views", title: "Database · belief timeline", icon: "timeline", run: () => go("#/database/timeline") },
    { group: "Views", title: "Add data", icon: "add", run: () => go("#/add") },
    { group: "Views", title: "Audit log", icon: "ledger", run: () => go("#/audit") },
    { group: "Actions", title: "Verify the ledger's hash chain", icon: "verify", keywords: "audit chain", run: () => go("#/audit?verify=1") },
    { group: "Actions", title: "Switch light / dark theme", icon: "pulse", keywords: "theme", run: () => theme(document.documentElement.dataset.theme === "dark" ? "light" : "dark") },
    { group: "Actions", title: "Sign out of this brain", icon: "lock", keywords: "logout", run: signOut },
  ];
  for (const a of state.agents) cmds.push({ group: "Agents", title: a.name, tier: a.tier, keywords: a.model, run: () => go(`#/agents?agent=${a.id}`) });
  return cmds;
}

let findTimer = 0;
async function openPalette() {
  if (!state.palette) {
    state.palette = ui.CommandPalette({ items: staticCommands(), onChoose: (it) => it.run && it.run(), onQuery: (q) => {
      clearTimeout(findTimer);
      findTimer = setTimeout(async () => {
        const base = staticCommands();
        if (q.length < 2) { state.palette.setItems(base); return; }
        try {
          const r = await api(`/api/find?q=${encodeURIComponent(q)}`);
          const found = [
            ...r.people.map((p) => ({ group: "People", title: p.name, icon: "person", meta: `${p.n_items} items`, always: true, run: () => go(`#/database/timeline?person=${encodeURIComponent(p.name)}`) })),
            ...r.beliefs.map((b) => ({ group: "Beliefs", title: b.statement, icon: "timeline", meta: b.kind, always: true, run: () => go(`#/database/constellation?belief=${b.id}`) })),
            ...r.items.map((i) => ({ group: "Items", title: i.subject || "(no subject)", icon: "note", meta: `item:${i.id}`, always: true, run: () => go(`#/database/constellation?item=${i.id}`) })),
          ];
          state.palette.setItems([...base, ...found]);
        } catch { /* keep the static list */ }
      }, 160);
    } });
  }
  if (!state.agents.length) { try { state.agents = await api("/api/agents"); } catch { /* fine */ } }
  state.palette.setItems(staticCommands());
  state.palette.open();
}
on("agents", (a) => { state.agents = a; });

boot();
