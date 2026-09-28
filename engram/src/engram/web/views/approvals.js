// An approval card for one action the gate escalated (from /api/pending). It resolves itself when the decision is
// recorded — here, or on the paired watch — and removes itself a moment later.
import * as ui from "../lib/ui.js";
import { api, on } from "../lib/api.js";

const RISK = { read: "read", internal: "internal", external: "external", destructive: "destructive" };

export function approvalCard(p, onGone) {
  const j = p.judge;
  const why = p.effect === "destructive"
    ? "Destructive: code always sends these to you, and only this laptop can approve them."
    : j ? `Intent check: ${j.value || "no answer"} at p ${Number(j.p).toFixed(2)}${j.settled ? "" : " — unsure, so it comes to you"}.`
      : "Its risk tier is above what the agent may do alone.";
  let done = false;
  const card = ui.ApprovalCard({
    request: p.request, preview: p.preview, risk: RISK[p.effect] || p.effect, why,
    channels: p.on_watch ? "your watch" : null,
    onApprove: () => decide(true), onDeny: () => decide(false),
  });
  card.dataset.run = p.run;
  async function decide(approve) {
    card.querySelectorAll("button").forEach((b) => { b.disabled = true; });
    try { await api(`/api/act/${p.run}/decide`, { approve }); finish(); }
    catch (e) {
      card.classList.remove("resolved");
      card.querySelectorAll("button").forEach((b) => { b.disabled = false; });
      card.append(ui.h("p", { class: "why", role: "alert", text: e.message }));
    }
  }
  function finish() {
    if (done) return;
    done = true;
    stopDecided(); stopPending();
    setTimeout(() => {
      ui.settle(ui.anim(card, [{ opacity: 1 }, { opacity: 0 }], { duration: ui.reducedMotion() ? 100 : 300, fill: "forwards" }), 900)
        .then(() => { card.remove(); onGone && onGone(); });
    }, 2400);
  }
  const stopDecided = on("decided", (d) => {
    if (d.run !== p.run || done) return;
    card.resolve(d.approved, d.channel);
    if (d.channel === "watch") card.querySelector(".done span:last-child").textContent += ` (${d.device || "watch"})`;
    finish();
  });
  const stopPending = on("pending", (list) => {             // decided elsewhere and the ledger row not seen yet
    if (!done && !list.some((x) => x.run === p.run)) setTimeout(() => { if (!done) { card.classList.add("resolved"); card.querySelector(".done span:last-child").textContent = "No longer waiting: decided or timed out"; finish(); } }, 4000);
  });
  return card;
}
