// Audit: the hash-chained ledger of judgements. Filter by tier, decision, actor and time; scroll for older rows (keyset
// paging on before_id); new rows arrive at the top. Verify chain asks the server to check the whole chain and scans the
// links on screen; at a break it stops, the link glows and the row says what failed.
import * as ui from "../lib/ui.js";
import { api, on } from "../lib/api.js";

export function mount(root, ctx) {
  const stops = [];
  const f = { tiers: new Set(["S1", "S2", "H"]), question: "", actor: "", since: "", until: "" };
  const tierBtns = ["S1", "S2", "H"].map((t) => {
    const chip = ui.TierChip({ tier: t, label: `${t} · ${ui.TIER_NAME[t]}` });
    const b = ui.h("button", { type: "button", class: chip.className + " filter-chip", "aria-pressed": "true" }, ...chip.childNodes);
    b.addEventListener("click", () => { f.tiers.has(t) ? f.tiers.delete(t) : f.tiers.add(t); b.setAttribute("aria-pressed", String(f.tiers.has(t))); reload(); });
    return b;
  });
  const question = ui.h("select", { class: "eg-input", "aria-label": "Decision" }, ui.h("option", { value: "", text: "every decision" }));
  const actor = ui.h("input", { class: "eg-input", placeholder: "actor, e.g. owner:watch", "aria-label": "Actor", list: "actors", autocomplete: "off" });
  const actors = ui.h("datalist", { id: "actors" }, ...["owner:page", "owner:watch", "qwen3:14b", "qwen3:1.7b", "mlx:"].map((v) => ui.h("option", { value: v })));
  const since = ui.h("input", { class: "eg-input", type: "date", "aria-label": "From date" });
  const until = ui.h("input", { class: "eg-input", type: "date", "aria-label": "Until date" });
  const verify = ui.Button({ label: "Verify chain", icon: "verify", variant: "utility", onClick: runVerify });
  const exp = ui.Button({ label: "Export JSONL", icon: "export", variant: "pearl", onClick: () => { L.exportJSONL(); ctx.announce(`${L.rows().length} rows exported`); } });
  const verdict = ui.h("span", { class: "eg-verdict", "aria-live": "polite" });
  const count = ui.h("span", { class: "hint eg-mono" });
  const L = ui.LedgerChain({ rows: [], bar: false });
  const sentinel = ui.h("div", { class: "sentinel" });
  const more = ui.Button({ label: "Load older rows", variant: "pearl", onClick: () => page() });
  root.append(ui.h("section", { class: "view audit-view" },
    ui.h("header", { class: "view-head" }, ui.h("div", null, ui.h("p", { class: "eg-caps", text: "hash-chained ledger" }),
      ui.h("h2", { class: "display", text: "Audit log" }), ui.h("p", { class: "lead", text: "Every judgement, linked to the one before it. Change a row and the chain breaks from there." }))),
    ui.h("div", { class: "audit-bar" },
      ui.h("div", { class: "filters", role: "group", "aria-label": "Filters" }, ...tierBtns, question, actor, actors, since, until),
      ui.h("div", { class: "actions" }, verdict, exp, verify)),
    L, ui.h("div", { class: "audit-foot" }, count, more), sentinel));

  api("/api/ledger/questions").then((qs) => question.append(...qs.map((q) => ui.h("option", { value: q, text: q })))).catch(() => {});
  let t = 0;
  const later = () => { clearTimeout(t); t = setTimeout(reload, 250); };
  question.addEventListener("change", () => { f.question = question.value; reload(); });
  actor.addEventListener("input", () => { f.actor = actor.value.trim(); later(); });
  since.addEventListener("change", () => { f.since = since.value; reload(); });
  until.addEventListener("change", () => { f.until = until.value; reload(); });

  let oldest = null, done = false, loading = false, gen = 0;
  const query = (extra) => {
    const q = new URLSearchParams({ limit: "60", ...extra });
    if (f.tiers.size < 3) q.set("tier", [...f.tiers].join(",") || "none");
    if (f.question) q.set("question", f.question);
    if (f.actor) q.set("actor", f.actor);
    if (f.since) q.set("since", f.since);
    if (f.until) q.set("until", f.until);
    return q.toString();
  };
  async function reload() {
    gen++; oldest = null; done = false;
    L.setRows([]);
    verdict.textContent = "";
    await page();
  }
  async function page() {
    if (loading || done) return;
    loading = true;
    const g = gen;
    try {
      const r = await api(`/api/ledger?${query(oldest ? { before_id: String(oldest) } : {})}`);
      if (g !== gen) return;
      if (r.rows.length) { L.append(r.rows); oldest = r.rows[r.rows.length - 1].id; }
      if (r.rows.length < 60) done = true;
      count.textContent = `${L.rows().length} rows${done ? " · the start of the chain" : ""}`;
      more.hidden = done;
      if (!L.rows().length) count.textContent = "No judgements match these filters.";
    } catch (e) { count.textContent = e.message; } finally { loading = false; }
  }
  const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) page(); }, { rootMargin: "400px" });
  io.observe(sentinel);
  stops.push(() => io.disconnect());

  const matches = (r) => f.tiers.has(r.tier) && (!f.question || r.question === f.question) && (!f.actor || r.model.toLowerCase().includes(f.actor.toLowerCase())) && !f.until;
  stops.push(on("ledger", (rows) => { for (const r of rows) if (matches(r)) L.prepend(r); count.textContent = `${L.rows().length} rows`; }));

  async function runVerify() {
    verify.disabled = true;
    verdict.className = "eg-verdict";
    verdict.textContent = "Checking the whole chain…";
    try {
      const r = await api("/api/ledger?verify=1");
      await L.verify({ first_bad: r.first_bad });
      verdict.textContent = "";
      if (r.intact) { verdict.className = "eg-verdict ok"; verdict.append(ui.Icon("check", { size: "sm" }), ` Chain intact: all ${ui.fmt(r.judgements)} judgements verified`); }
      else { verdict.className = "eg-verdict bad"; verdict.append(ui.Icon("alert", { size: "sm" }), ` Broken at judgement ${r.first_bad}: rows from there on can't be trusted`); }
    } catch (e) { verdict.textContent = e.message; }
    verify.disabled = false;
  }
  reload().then(() => { if (ctx.params.get("verify")) runVerify(); });
  return { route: (sub, p) => { if (p.get("verify")) runVerify(); }, unmount: () => { stops.forEach((s) => s()); clearTimeout(t); } };
}
