// Agents: the switchboard. Every agent sits in its tier's lane (S0 code → S1 small judge → S2 large model → H you),
// tagged with its roster role (Librarian, Researcher, Memory, Planner, Operator, Guardian, Herald, Diplomat); a role
// filter lights one role's cards across the lanes. Each new ledger row fires a particle along the path that decision
// really took. Below, the roles you work with: what waits on you and Herald's cards; the Operator (a WorkBench task,
// or a meeting request answered by the roles as one pipeline); and the Planner's day.
import * as ui from "../lib/ui.js";
import { api, every, on } from "../lib/api.js";
import { approvalCard } from "./approvals.js";

const ROLE_STEP = /^(Librarian|Researcher|Memory|Planner|Operator|Writer|Guardian|Fact Checker|Herald|Diplomat)$/;

export function mount(root, ctx) {
  const stops = [];
  const board = ui.h("div", { class: "board-slot" }, ui.h("p", { class: "loading", text: "Reading the agents' state…" }));
  const approvals = ui.h("div", { class: "approval-list" });
  const drawerHost = ui.h("div", { class: "drawer-host" });
  const runOut = ui.h("div", { class: "run-out", "aria-live": "polite" });
  const request = ui.h("input", { class: "eg-input", type: "text", name: "request", placeholder: "Forward my most recent email from fatima to kofi", "aria-label": "Task for the agent", autocomplete: "off" });
  const autonomy = ui.h("select", { class: "eg-input", "aria-label": "What the agent may do without asking" },
    ui.h("option", { value: "0", text: "Ask me before anything that writes" }),
    ui.h("option", { value: "1", text: "May change internal things alone", selected: true }));
  // WorkBench's own tool selection: the task's toolkits (the company directory always comes along); all of them
  // at once leaves the 14B choosing among ~70 tools, and it tends to look things up and stop
  const toolkit = ui.h("select", { class: "eg-input", "aria-label": "Toolkits the agent may use" },
    ...[["email", "Email"], ["calendar", "Calendar"], ["customer_relationship_manager", "CRM"], ["project_management", "Projects"],
      ["analytics", "Analytics"], ["", "All toolkits"]].map(([v, t]) => ui.h("option", { value: v, text: t })));
  const form = ui.h("form", { class: "act-form" }, request, toolkit, autonomy, ui.Button({ label: "Run", type: "submit" }));
  const taskBody = ui.h("div", null,
    ui.h("p", { class: "hint", text: "The large model proposes one tool call at a time in the WorkBench sandbox. Code sets each call's risk; anything it may not do alone comes to you." }),
    form);
  const meetingBody = ui.h("div", { hidden: true });
  const opSeg = ui.Segmented({ label: "Operator", options: [{ value: "task", label: "Agent task" }, { value: "meeting", label: "Meeting reply" }],
    onChange: (v) => { taskBody.hidden = v !== "task"; meetingBody.hidden = v !== "meeting"; if (v === "meeting") loadInbox(); } });
  const heraldList = ui.h("div", { class: "herald-list", "aria-live": "polite" });
  const planHost = ui.h("div", { class: "plan-host" });

  const ROLES = ["Librarian", "Researcher", "Memory", "Planner", "Operator", "Guardian", "Herald", "Diplomat"];
  const roleBar = ui.h("div", { class: "role-filter", role: "group", "aria-label": "Show one role" },
    ...[null, ...ROLES].map((r) => ui.h("button", { type: "button", "aria-pressed": String(r === null), "data-role": r || "", text: r || "All roles",
      onClick: (e) => { roleBar.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === e.currentTarget))); sb && sb.filter(r); } })));

  root.append(ui.h("section", { class: "view agents-view" },
    ui.h("header", { class: "view-head" },
      ui.h("div", null, ui.h("p", { class: "eg-caps", text: "S0 → S1 → S2 → H" }),
        ui.h("h2", { class: "display", text: "Switchboard" }),
        ui.h("p", { class: "lead", text: "Every judgement, the tier that settled it, and the role that asked." }))),
    roleBar,
    board,
    ui.h("div", { class: "agents-lower" },
      ui.h("div", { class: "stack" },
        ui.h("section", { class: "panel", "aria-labelledby": "wait-h" }, ui.h("h3", { class: "tagline", id: "wait-h", text: "Waiting on you" }), approvals),
        ui.h("section", { class: "panel", "aria-labelledby": "herald-h" },
          ui.h("div", { class: "panel-head" }, ui.h("h3", { class: "tagline", id: "herald-h", text: "Herald" }), ui.h("span", { class: "eg-caps", text: "the same cards as your watch" })),
          heraldList)),
      ui.h("section", { class: "panel", "aria-labelledby": "act-h" },
        ui.h("div", { class: "panel-head" }, ui.h("h3", { class: "tagline", id: "act-h", text: "Operator" }), opSeg),
        taskBody, meetingBody, runOut)),
    ui.h("section", { class: "panel plan-panel", "aria-labelledby": "plan-h" },
      ui.h("div", { class: "panel-head" }, ui.h("h3", { class: "tagline", id: "plan-h", text: "Planner · the day" }),
        ui.h("span", { class: "eg-caps", text: "OR-Tools CP-SAT around meetings; the judge keeps real to-dos" })),
      planHost)),
    drawerHost);

  /* ----------------------------------------------------------------- the board */
  let sb = null, agents = [];
  const lastAgent = new Map();                            // question|subject -> the agent that judged it last
  const remember = (r) => lastAgent.set(`${r.question}|${r.subject}`, r.agent);
  stops.push(on("ledger-history", (rows) => rows.forEach(remember)));

  function foot(list) {
    const today = list.reduce((n, a) => n + (a.id !== "parser" && a.today ? a.today : 0), 0);
    const watch = list.find((a) => a.id === "watch");
    const waiting = list.find((a) => a.id === "owner")?.pending || 0;
    return [["decisions today", ui.fmt(today)], ["waiting on you", String(waiting)], ["watch", watch ? watch.model : "—"]];
  }
  function laneMeta(list) {
    const m = {};
    for (const t of ui.TIERS) {
      const p = list.filter((a) => a.tier === t && a.p50 != null).map((a) => a.p50);
      m[t] = t === "S0" ? "code" : p.length ? `p50 ${Math.min(...p)}${p.length > 1 && Math.max(...p) !== Math.min(...p) ? "–" + Math.max(...p) : ""} ms` : "no decisions yet";
    }
    return m;
  }
  stops.push(every(2500, async () => {
    agents = await api("/api/agents");
    window.dispatchEvent(new CustomEvent("engram:agents", { detail: agents }));
    if (!sb) {
      sb = ui.Switchboard({ agents, laneMeta: laneMeta(agents), foot: foot(agents), onSelect: (a) => openDrawer(a.id) });
      board.replaceChildren(sb);
      const want = ctx.params.get("agent");
      if (want) openDrawer(want);
    } else {
      sb.update(agents);
      sb.setFoot(foot(agents));
      sb.querySelectorAll(".eg-lane").forEach((lane) => { lane.querySelector(".m").textContent = laneMeta(agents)[lane.dataset.tier]; });
    }
  }));

  // particles: one per new ledger row, along its real path; a burst is thinned to the latest few
  const queue = [];
  let firing = false;
  async function drain() {
    if (firing || !sb) return;
    firing = true;
    while (queue.length) {
      if (queue.length > 5) queue.splice(0, queue.length - 5);
      const { path, row } = queue.shift();
      if (row.agent === "watch") sb.flash("watch");
      await sb.fire(path, { say: `${row.question} → ${row.value} settled by ${row.tier}` });
    }
    firing = false;
  }
  stops.push(on("ledger", (rows) => {
    for (const r of rows) {
      const before = lastAgent.get(`${r.question}|${r.subject}`);
      const path = [r.entry];
      if (before && before !== r.agent) path.push(before);
      path.push(r.agent);
      remember(r);
      queue.push({ path, row: r });
    }
    drain();
    if (drawer && rows.some((r) => r.agent === drawer.dataset.agent)) openDrawer(drawer.dataset.agent, true);
  }));

  /* ----------------------------------------------------------------- the drawer */
  let drawer = null, opener = null;
  async function openDrawer(id, refresh) {
    let a;
    try { a = await api(`/api/agents/${encodeURIComponent(id)}`); } catch { return; }
    if (!refresh) opener = document.activeElement;
    const pend = ctx.pending().filter(() => a.status === "waiting" && (a.id === "workbench" || a.id === "owner"));
    const next = ui.AgentDrawer({
      agent: a, latencies: a.latencies, decisions: a.decisions,
      onClose: closeDrawer,
      onApprove: pend.length ? () => decide(pend[0].run, true) : null,
      onDeny: pend.length ? () => decide(pend[0].run, false) : null,
    });
    next.dataset.agent = id;
    next.classList.add("drawer");
    const facts = ui.h("dl", { class: "drawer-facts" },
      ui.h("dt", { class: "eg-caps", text: "status" }), ui.h("dd", { text: a.status + (a.task ? ` · ${a.task}` : "") }),
      ui.h("dt", { class: "eg-caps", text: "last decision" }), ui.h("dd", { class: "eg-mono", text: a.last ? `${a.last.question} → ${a.last.value}` : "none yet" }));
    next.insertBefore(facts, next.children[2] || null);
    if (!a.decisions.length) next.querySelector(".eg-dlist").replaceWith(ui.h("p", { class: "hint", text: a.tier === "S0" ? "Code decides here: it makes no model judgements, so it writes no ledger rows." : "No decisions in the ledger yet." }));
    if (drawer) drawer.replaceWith(next); else { drawerHost.append(next); if (!ui.reducedMotion()) ui.anim(next, [{ transform: "translateX(24px)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 240, easing: ui.css("ease-standard") }); }
    drawer = next;
    if (!refresh) (drawer.querySelector("h3") || drawer).setAttribute("tabindex", "-1"), drawer.querySelector("h3").focus();
  }
  function closeDrawer() {
    if (!drawer) return;
    drawer.remove();
    drawer = null;
    opener && opener.focus && opener.focus();
  }
  async function decide(run, approve) {
    try { await api(`/api/act/${run}/decide`, { approve }); } catch (e) { ctx.announce(e.message); }
  }
  const esc = (e) => { if (e.key === "Escape" && drawer) closeDrawer(); };
  document.addEventListener("keydown", esc);
  stops.push(() => document.removeEventListener("keydown", esc));

  /* ----------------------------------------------------------------- approvals */
  const cards = new Map();
  function renderApprovals(list) {
    for (const p of list) {
      if (cards.has(p.run)) continue;
      const c = approvalCard(p, () => { cards.delete(p.run); empty(); });
      cards.set(p.run, c);
      approvals.append(c);
    }
    empty();
  }
  function empty() {
    const e = approvals.querySelector(".empty");
    if (!cards.size && !e) approvals.append(ui.h("p", { class: "empty", text: "Nothing is waiting on you." }));
    if (cards.size && e) e.remove();
  }
  renderApprovals(ctx.pending());
  stops.push(on("pending", renderApprovals));

  /* ----------------------------------------------------------------- a task for the agent */
  let runTimer = 0;
  async function start(path, body) {
    runOut.textContent = "";
    clearInterval(runTimer);
    try {
      const { id } = await api(path, body);
      const poll = async () => {
        const r = await api(`/api/act/${id}`);
        renderRun(r);
        if (r.status === "done" || r.status === "error") clearInterval(runTimer);
      };
      runTimer = setInterval(poll, 1000);
      poll();
    } catch (ex) {
      runOut.append(ui.h("p", { class: "error", role: "alert", text: ex.message }));
    }
  }
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = request.value.trim();
    if (!q) { request.focus(); return; }
    start("/api/act", { request: q, autonomy: Number(autonomy.value), ...(toolkit.value ? { domains: [toolkit.value] } : {}) });
  });
  function renderRun(r) {
    runOut.textContent = "";
    const list = ui.h("ol", { class: "steps" });
    for (const s of r.steps) {
      const g = s.gate;
      if (!g && ROLE_STEP.test(s.tool)) {                  // a step of the meeting pipeline: the role, and what it did
        list.append(ui.h("li", null,
          ui.h("div", { class: "step-head" }, ui.h("span", { class: "role-tag", text: s.tool }), s.ms != null ? ui.h("span", { class: "eg-mono hint", text: `${Math.round(s.ms)} ms` }) : null),
          ui.h("p", { class: "obs plain", text: s.observation })));
        continue;
      }
      list.append(ui.h("li", null,
        ui.h("div", { class: "step-head" }, ui.h("span", { class: "eg-mono", text: s.tool }),
          g && g.judge ? ui.TierChip({ tier: g.judge.tier || "S2" }) : ui.TierChip({ tier: "S0", label: "S0 · code" }),
          ui.h("span", { class: "eg-caps", text: s.ran ? "ran" : "stopped" })),
        g ? ui.h("p", { class: "hint", text: g.reason }) : null,
        ui.h("pre", { class: "obs", text: s.observation })));
    }
    runOut.append(list);
    runOut.prepend(ui.h("p", { class: "eg-caps", text: r.request }));
    if (r.status === "waiting") runOut.append(ui.h("p", { class: "hint", text: "Waiting on you: approve or deny it under Waiting on you, or on your watch." }));
    else if (r.status === "running") runOut.append(ui.h("p", { class: "hint", text: "The agent is working…" }));
    else runOut.append(ui.h("p", { class: r.status === "error" ? "error" : "answer", text: r.answer }));
  }

  /* ----------------------------------------------------------------- Operator: a meeting request, answered */
  let inbox = null;
  const pick = ui.h("select", { class: "eg-input", "aria-label": "A meeting request in the inbox" });
  const preview = ui.h("pre", { class: "mail-preview" });
  const own = { sender: ui.h("input", { class: "eg-input", placeholder: "from, e.g. nia.johnson@atlas.com", "aria-label": "Sender" }),
    subject: ui.h("input", { class: "eg-input", placeholder: "subject", "aria-label": "Subject" }),
    body: ui.h("textarea", { class: "eg-input", rows: "4", placeholder: "Hi Sam, can we meet Thursday at 2 pm to …", "aria-label": "Request" }) };
  const answerBtn = ui.Button({ label: "Answer it", type: "submit" });
  const meetingForm = ui.h("form", { class: "meeting-form" },
    ui.h("p", { class: "hint", text: "The roles as one pipeline: the Librarian reads the request, the Researcher checks how much you deal with the sender, the Planner finds a free slot, the Writer drafts, code checks the draft, and the gate brings the reply to you." }),
    pick, preview,
    ui.h("details", { class: "own-request" }, ui.h("summary", { text: "Or write a request of your own" }), own.sender, own.subject, own.body),
    ui.h("div", { class: "row" }, answerBtn));
  meetingBody.append(meetingForm);
  pick.addEventListener("change", () => { const m = inbox && inbox.find((x) => x.email_id === pick.value); preview.textContent = m ? `${m.sender} · ${m.sent}\n${m.subject}\n\n${m.body}` : ""; });
  async function loadInbox() {
    if (inbox) return;
    try { inbox = await api("/api/meeting/inbox"); } catch (e) { inbox = []; preview.textContent = e.message; }
    pick.replaceChildren(...(inbox.length ? inbox.map((m) => ui.h("option", { value: m.email_id, text: `${m.sender.split("@")[0]} · ${m.subject}` }))
      : [ui.h("option", { value: "", text: "No meeting requests in the WorkBench inbox" })]));
    pick.dispatchEvent(new Event("change"));
  }
  meetingForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const mine = own.sender.value.trim() && own.body.value.trim();
    if (!mine && !pick.value) return;
    start("/api/meeting", mine ? { sender: own.sender.value.trim(), subject: own.subject.value.trim(), body: own.body.value.trim() } : { email_id: pick.value });
  });

  /* ----------------------------------------------------------------- Herald: the watch's cards, here too */
  async function loadHerald() {
    let list;
    try { list = await api("/api/herald"); } catch (e) { heraldList.replaceChildren(ui.h("p", { class: "error", text: e.message })); return; }
    if (!list.length) { heraldList.replaceChildren(ui.h("p", { class: "empty", text: "No cards. Memory posts one when a commitment is due within the hour or a check is unsure, and the Librarian when a fresh item holds a meeting." })); return; }
    const shown = list.slice(0, 8);
    heraldList.replaceChildren(...shown.map(heraldCard), list.length > shown.length ? ui.h("p", { class: "hint", text: `and ${list.length - shown.length} more in the digest` }) : "");
  }
  function heraldCard(c) {
    const acts = ui.h("div", { class: "row" }, ...c.actions.map((a) => ui.Button({ label: a.label, variant: a.id === c.actions[0].id ? "primary" : "secondary", className: "small",
      onClick: async () => {
        acts.querySelectorAll("button").forEach((b) => { b.disabled = true; });
        try { await api(`/api/herald/${c.id}`, { action: a.id }); ctx.announce(`${c.title}: ${a.label}`); } catch (e) { ctx.announce(e.message); }
        loadHerald();
      } })));
    return ui.h("article", { class: "herald-card" + (c.route === "now" ? " now" : "") },
      ui.h("div", { class: "herald-top" }, ui.h("span", { class: "role-tag", text: c.role }), ui.h("span", { class: "eg-caps", text: c.route === "now" ? "buzzed" : "digest" }), ui.h("span", { class: "hint eg-mono", text: c.created_at.slice(0, 16).replace("T", " ") })),
      ui.h("b", { text: c.title }), ui.h("p", { class: "body", text: c.body }), c.why ? ui.h("p", { class: "hint", text: c.why }) : null, acts);
  }
  loadHerald();
  stops.push(every(6000, loadHerald));

  /* ----------------------------------------------------------------- Planner: the day, placed by CP-SAT */
  const dayIn = ui.h("input", { class: "eg-input", type: "date", "aria-label": "Day" });
  const atIn = ui.h("input", { class: "eg-input", type: "time", "aria-label": "Re-plan at (the owner's time)", value: "13:00" });
  const planOut = ui.h("div", { class: "plan-out", "aria-live": "polite" });
  const planBtn = ui.Button({ label: "Plan the day", variant: "utility", onClick: () => replan(false) });
  const replanBtn = ui.Button({ label: "Re-plan from", variant: "pearl", onClick: () => replan(true) });
  planHost.append(ui.h("div", { class: "plan-bar" }, dayIn, planBtn, ui.h("span", { class: "sep" }), replanBtn, atIn), planOut);
  dayIn.addEventListener("change", () => showPlan(dayIn.value));
  async function showPlan(day) {
    try { renderPlan(await api(`/api/plan${day ? `?day=${day}` : ""}`)); } catch (e) { planOut.replaceChildren(ui.h("p", { class: "error", text: e.message })); }
  }
  async function replan(fromNow) {
    if (!dayIn.value) return;
    planBtn.disabled = replanBtn.disabled = true;
    planOut.prepend(ui.h("p", { class: "hint", text: "Solving… the judge checks each commitment is a real to-do (cached after the first plan)." }));
    try { renderPlan(await api("/api/plan", { day: dayIn.value, ...(fromNow ? { now: atIn.value } : {}) })); }
    catch (e) { planOut.prepend(ui.h("p", { class: "error", role: "alert", text: e.message })); }
    planBtn.disabled = replanBtn.disabled = false;
  }
  const mins = (hm) => { const [h, m] = hm.split(":").map(Number); return h * 60 + m; };
  function renderPlan(p) {
    if (p.day) dayIn.value = p.day;
    if (!p.entries.length) { planOut.replaceChildren(ui.h("p", { class: "empty", text: p.day ? `Nothing planned for ${p.day} yet. Plan the day to place its open commitments around its meetings.` : "No day planned yet. Pick a day and plan it." })); return; }
    const placed = p.entries.filter((e) => e.starts);
    const lo = Math.min(8 * 60, ...placed.map((e) => mins(e.starts))), hi = Math.max(18 * 60, ...placed.map((e) => mins(e.ends)));
    const pct = (m) => `${((m - lo) / (hi - lo)) * 100}%`;
    const strip = ui.h("div", { class: "plan-strip", "aria-hidden": "true" },
      ...Array.from({ length: Math.floor((hi - lo) / 60) + 1 }, (_, i) => ui.h("span", { class: "hr", style: { left: pct(lo + i * 60) }, text: String(Math.floor(lo / 60) + i).padStart(2, "0") })),
      ...placed.map((e) => ui.h("span", { class: `blk ${e.kind} ${e.status}`, title: `${e.starts}–${e.ends} ${e.title}`, style: { left: pct(mins(e.starts)), width: pct(lo + mins(e.ends) - mins(e.starts)) } })));
    const rows = ui.h("ol", { class: "plan-list" }, ...p.entries.map((e) => ui.h("li", { class: `${e.kind} ${e.status}` },
      ui.h("span", { class: "eg-mono when", text: e.starts ? `${e.starts}–${e.ends}` : "didn't fit" }),
      ui.h("span", { class: "kind", text: e.kind }),
      ui.h("span", { class: "what" }, ui.h("b", { text: e.title }), e.why ? ui.h("span", { class: "hint", text: e.why }) : null),
      e.status !== "planned" ? ui.h("span", { class: `st ${e.status}`, text: e.status }) : ui.h("span"))));
    planOut.replaceChildren(ui.h("p", { class: "eg-caps", text: `${p.day} · plan v${p.version} · ${p.timezone}${p.seconds != null ? ` · solved in ${p.seconds} s` : ""}` }), strip, rows);
  }
  showPlan();

  return {
    route: (sub, params) => { const a = params.get("agent"); if (a) openDrawer(a); },
    unmount: () => { stops.forEach((s) => s()); clearInterval(runTimer); for (const c of cards.values()) c.remove(); },
  };
}
