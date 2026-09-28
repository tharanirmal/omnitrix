const DECISIONS = ["remember", "meeting_request", "fulfilled", "contradicts", "todo"];
let current = DECISIONS[0], example = null, busy = false;
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

async function load() {
  const res = await fetch(`/api/label/next?question=${current}`);
  if (res.status === 401) {               // the labels belong to a brain: open one on the main page first
    document.getElementById("card").innerHTML =
      `<div class="q">Sign in to a brain on <a href="/">the main page</a> first, then come back to /label.</div>`;
    return;
  }
  const r = await res.json();
  example = r.example;
  document.getElementById("tabs").innerHTML = DECISIONS.map(d => {
    const p = r.progress[d] || {queued: 0, checked: 0};
    return `<button data-d="${d}" class="${d === current ? "on" : ""}">${d}<small>${p.checked} / ${p.queued} checked</small></button>`;
  }).join("");
  document.getElementById("card").innerHTML = example
    ? `<div class="q">${esc(example.instructions)}</div><pre>${esc(example.state)}</pre>`
    : `<div class="q">Nothing left to check for <b>${current}</b>.</div>`;
}

async function answer(value) {
  if (!example || busy) return;
  busy = true;
  try {
    await fetch("/api/label", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: current, subject: example.subject, value})});
    await load();
  } finally { busy = false; }
}

document.getElementById("tabs").addEventListener("click", e => {
  const b = e.target.closest("button[data-d]"); if (b) { current = b.dataset.d; load(); }
});
document.querySelector(".bar").addEventListener("click", e => {
  const b = e.target.closest("button[data-v]"); if (b) answer(b.dataset.v);
});
document.addEventListener("keydown", e => {
  const v = {y: "yes", n: "no", s: "skip"}[e.key.toLowerCase()];
  if (v && !e.metaKey && !e.ctrlKey) answer(v);
});
load();
