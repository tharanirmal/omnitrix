// Presenter mode for the demo video: open the page with ?demo, then press → (or Space) for each beat while you talk.
// Every beat drives the real page (the same buttons and fields a person uses, the real models); nothing is faked.
// A lower-third caption names what is on screen, so the video reads without sound. H hides the captions, Esc leaves.
// ?demo=5 starts at beat 5, to reshoot from there (signed in already).
// The voice script that goes with these beats is docs/demo/demo-script.md.
import * as ui from "./lib/ui.js";
import { api } from "./lib/api.js";

const QUESTION = "Where and at what time did Vince suggest meeting Michael Garberding on Tuesday?";
const EMAIL = {                                  // the same text again collapses into the same item (read once)
  title: "Kenneth's interview",
  from: "shirley.crenshaw@enron.com",
  date: "2001-04-02",
  text: "Vince,\n\nKenneth's interview is confirmed for Monday at 10 am in EB1972. I will send the interview " +
    "schedule to Stinson and Paulo by Friday, and Tanya will join you both for lunch afterwards.\n\nShirley",
};
const MEETING_EMAIL = "00000066";                 // Nia Johnson asks for a project checkpoint (WorkBench inbox)

const $ = (sel) => document.querySelector(sel);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(test, ms = 90000) {         // the real models set the pace: wait for what they produce
  const t0 = performance.now();
  while (performance.now() - t0 < ms) { const v = test(); if (v) return v; await sleep(150); }
  throw new Error("timed out");
}
async function go(hash) { if (location.hash !== hash) location.hash = hash; await sleep(700); }
function see(el) { el && el.scrollIntoView({ behavior: "smooth", block: "center" }); return sleep(700); }
async function type(el, text, per = 28) {
  el.focus();
  el.value = "";
  for (const ch of text) { el.value += ch; el.dispatchEvent(new Event("input", { bubbles: true })); await sleep(per); }
}
const button = (root, label) => [...(root || document).querySelectorAll("button")].find((b) => b.innerText.trim() === label);

/* ------------------------------------------------------------------------------------------------ the beats */
const BEATS = [
  { cap: ["engram", "A sovereign second brain. Everything you will see runs on this Mac."],
    run: async () => { if (document.body.dataset.mode === "dashboard") { button(null, "Sign out")?.click(); await until(() => $(".eg-profile")); } } },

  { cap: ["Sign in", "Each brain is its own Postgres database, opened with its own passphrase."],
    run: async () => {
      const tile = await until(() => [...document.querySelectorAll(".eg-profile")].find((t) => t.dataset.name === "kaminski"));
      tile.click();
      await until(() => document.body.dataset.mode === "dashboard", 120000);   // you type the passphrase
      await sleep(2500);
    } },

  { cap: ["Ask", "Search → the fine-tuned 1.7B judge drops what is irrelevant → the 14B answers → the judge checks the answer."],
    run: async () => {
      await go("#/database/constellation");
      const input = await until(() => $(".ask-form input"));
      await type(input, QUESTION);
      await sleep(300);
      $(".ask-form").requestSubmit();
      await until(() => $(".ask-out .answer"));
    } },

  { cap: ["Add data", "Searchable in milliseconds. The judge decides what is worth remembering; the 14B extracts it."],
    run: async () => {
      await go("#/add");
      const form = await until(() => $("#view form"));
      form.querySelector("[name=title]").value = EMAIL.title;
      form.querySelector("[name=from]").value = EMAIL.from;
      form.querySelector("[name=date]").value = EMAIL.date;
      await type(form.querySelector("[name=text]"), EMAIL.text, 9);
      await sleep(300);
      const seen = new Set((await api("/api/adds")).map((a) => a.id));
      form.requestSubmit();
      let done = false;                                   // the server says when it is done; the animation follows
      const poll = setInterval(async () => { try { done = (await api("/api/adds")).some((a) => !seen.has(a.id) && a.status !== "running"); } catch { /* next time */ } }, 1000);
      try { await until(() => done, 180000); } finally { clearInterval(poll); }
      await sleep(3000);
    } },

  { cap: ["Agents", "The roster's roles on four tiers: code, the small judge, the 14B, and you."],
    run: async () => {
      await go("#/agents");
      await until(() => $(".eg-agent"));
      for (const role of ["Guardian", "Planner", "Operator", null]) {
        [...document.querySelectorAll(".role-filter button")].find((b) => b.dataset.role === (role || ""))?.click();
        await sleep(1300);
      }
    } },

  { cap: ["Meeting reply", "Librarian → Researcher → Planner → Writer → Fact Checker. Nothing leaves without your approval."],
    run: async () => {
      await go("#/agents");                           // a reshoot from this beat starts on another view
      await see(await until(() => $("#act-h")));
      [...document.querySelectorAll(".panel-head [role=radio]")].find((b) => b.textContent === "Meeting reply")?.click();
      const pick = await until(() => { const s = $(".meeting-form select"); return s && s.querySelector(`option[value="${MEETING_EMAIL}"]`) && s; });
      pick.value = MEETING_EMAIL;
      pick.dispatchEvent(new Event("change"));
      await sleep(1200);
      const waiting = document.querySelectorAll(".approval-list [data-run]").length;
      $(".meeting-form").requestSubmit();
      await until(() => document.querySelectorAll(".approval-list [data-run]").length > waiting, 120000);
      await see($(".approval-list [data-run]:last-child"));
    } },

  { cap: ["Audit", "Every judgement is hash-chained, and the ledger is also the judge's training data."],
    run: async () => {
      await go("#/audit");
      const verify = await until(() => button(null, "Verify chain"));
      await sleep(800);
      verify.click();
      await until(() => /intact|Broken/.test($(".eg-verdict")?.textContent || ""));
    } },

  { cap: null, run: async () => showResults() },

  { cap: ["Your approval", "Approve here, or on your paired watch. Either way it goes into the ledger as a human decision."],
    run: async () => {
      hideResults();
      await go("#/agents");
      const card = await until(() => $(".approval-list [data-run]:last-child"));
      await see(card);
      await sleep(2500);
      button(card, "Approve")?.click();
      await until(() => card.classList.contains("resolved") || !card.isConnected, 20000);   // "Approved · … as H"
    } },

  { cap: ["engram", "Local models, your data, your last word. Every decision is on the ledger."],
    run: async () => { hideResults(); } },
];

/* ------------------------------------------------------------------------------------------------ results card */
const RESULTS = [
  ["96.6%", "the fine-tuned 1.7B judge on “supported”", "the zero-shot 14B: 95.5%, at 3–5× the latency"],
  ["84%", "of answers are right when the judge vouches", "6% when it doesn't: it knows when to escalate"],
  ["40% → 6.7%", "harmful side effects, agent alone → through the gate", "WorkBench, 60 fresh tasks"],
  ["13 ms", "from arriving to searchable", "11,528 emails ingested in 2.8 s, no model calls"],
];
let card = null;
function showResults() {
  hideResults();
  card = ui.h("section", { class: "demo-results eg-tile eg-ontile", "aria-label": "Measured results" },
    ui.h("p", { class: "eg-caps", text: "measured on this Mac · M5 Pro, 24 GB · the kaminski-v mailbox" }),
    ui.h("div", { class: "grid" }, ...RESULTS.map(([big, what, sub]) => ui.h("div", null,
      ui.h("b", { class: "eg-mono", text: big }), ui.h("span", { text: what }), ui.h("small", { text: sub })))));
  document.body.append(card);
  document.body.classList.add("demo-dim");
  if (!ui.reducedMotion()) ui.anim(card, [{ opacity: 0, transform: "translateY(12px)" }, { opacity: 1, transform: "none" }], { duration: 400, easing: ui.css("ease-standard") });
}
function hideResults() { card?.remove(); card = null; document.body.classList.remove("demo-dim"); }

/* ------------------------------------------------------------------------------------------------ the presenter */
export function start() {
  const from = Math.max(1, Math.min(BEATS.length, Number(new URLSearchParams(location.search).get("demo")) || 1));
  let i = from - 2, busy = false, hidden = false;
  const title = ui.h("b"), line = ui.h("span"), step = ui.h("small", { class: "eg-mono" });
  const cap = ui.h("div", { class: "demo-cap", role: "status", "aria-live": "polite" }, title, line, step);
  document.body.append(cap);
  cap.hidden = true;

  function caption(c) {
    cap.hidden = hidden || !c;
    if (!c) return;
    title.textContent = c[0]; line.textContent = c[1]; step.textContent = `${i + 1}/${BEATS.length}`;
    if (!ui.reducedMotion()) ui.anim(cap, [{ opacity: 0 }, { opacity: 1 }], { duration: 300 });
  }
  async function next() {
    if (busy || i >= BEATS.length - 1) return;
    busy = true;
    i += 1;
    caption(BEATS[i].cap);
    try { await BEATS[i].run(); } catch (e) { console.warn("demo beat", i + 1, e); }
    if (document.body.dataset.mode === "dashboard") document.activeElement?.blur?.();   // → must reach us next
    busy = false;
  }
  window.engramDemo = { get beat() { return i + 1; }, get busy() { return busy; }, beats: BEATS.length };   // for a recorder
  addEventListener("keydown", (e) => {
    if (e.target.matches?.("input, textarea, select") && e.target.type !== "radio") return;   // typing a passphrase
    if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); next(); }
    else if (e.key.toLowerCase() === "h") { hidden = !hidden; cap.hidden = hidden || !BEATS[i]?.cap; }
    else if (e.key === "Escape" && !document.querySelector(".eg-cmdk")) { cap.remove(); hideResults(); }
  });
}
