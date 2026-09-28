// The brains on this machine, as tiles. Each tile draws its own brain's shape (kinds and links only, no text), with
// its counts. Pick one, type its passphrase in the field that slides out of the tile, and the tile's constellation
// grows into the dashboard. A wrong passphrase shakes the tile and says how many tries are left.
import * as ui from "../lib/ui.js";
import { api } from "../lib/api.js";

let tiles = [];

export function unmount() {
  for (const t of tiles) t._sky && t._sky.stop();
  tiles = [];
}

const colorVar = (c) => `var(--tier-${c || "s1"})`;

export async function mount(root, { onUnlocked, collapseFrom }) {
  unmount();
  const grid = ui.h("div", { class: "login-tiles", role: "list" });
  const status = ui.h("p", { class: "login-status", role: "status" });
  root.append(ui.h("section", { class: "login" },
    ui.h("div", { class: "login-copy" },
      ui.h("p", { class: "eg-caps", text: "engram · a sovereign second brain" }),
      ui.h("h1", { class: "hero", text: "Your brain, on your machine." }),
      ui.h("p", { class: "login-lead", text: "Each brain is its own Postgres database on this computer, opened with its own passphrase. Small local models do the judging; you have the last word." }),
      ui.h("p", { class: "login-seal" }, ui.Icon("lock", { size: "sm" }), ui.h("span", { text: "Served on 127.0.0.1. Nothing on this page comes from, or goes to, the network." }))),
    grid, status));

  let profiles = [];
  try { profiles = (await api("/api/profiles")).profiles; }
  catch (e) { status.textContent = `Can't reach engram serve: ${e.message}`; }
  for (const p of profiles) {
    const tile = ui.ProfileTile({
      name: p.name, color: colorVar(p.color), counts: p.counts || {}, graph: p.graph,
      onUnlock: (pass, t) => unlock(p, pass, t, onUnlocked),
      onFocus: (t) => tiles.forEach((o) => { if (o !== t && o.classList.contains("is-focused")) o.blur_(); }),
    });
    tile.setAttribute("role", "listitem");
    if (p.error) tile.querySelector(".eg-profile-counts").replaceWith(ui.h("p", { class: "tile-note", text: `${p.error}.` }));
    tiles.push(tile);
    grid.append(tile);
  }
  grid.append(newBrainTile(onUnlocked));
  if (!profiles.length) status.textContent = "No brains yet. Make one here, or open an existing database from a terminal: engram profile add kaminski --database engram";
  if (collapseFrom) {
    const t = tiles.find((x) => x.dataset.name === collapseFrom);
    const p = profiles.find((x) => x.name === collapseFrom);
    if (t && p) collapseInto(t, p.graph);
  } else if (tiles.length === 1) {
    tiles[0].focus();
  }
}

async function unlock(p, pass, tile, onUnlocked) {
  const btn = tile.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const r = await api("/api/login", { profile: p.name, passphrase: pass });
    await onUnlocked(r.profile, tile);
  } catch (e) {
    btn.disabled = false;
    if (e.status === 401) {
      const n = e.body.remaining;
      await tile.reject(`That passphrase doesn't open ${p.name}. ${n} ${n === 1 ? "try" : "tries"} left before a pause.`);
    } else if (e.status === 429) {
      await tile.reject(`Too many wrong passphrases: ${p.name} is locked for ${e.body.retry_after} s.`);
      btn.disabled = true;
      setTimeout(() => { btn.disabled = false; }, e.body.retry_after * 1000);
    } else {
      await tile.reject(e.message);
    }
  }
}

/* Log out: a full-screen constellation shrinks back into the tile it came from. */
function collapseInto(tile, graph) {
  const to = tile.querySelector(".eg-profile-sky").getBoundingClientRect();
  const ghost = ui.h("div", { class: "eg-expand", style: { left: "0px", top: "0px", width: `${innerWidth}px`, height: `${innerHeight}px` } });
  const canvas = ui.h("canvas");
  ghost.append(canvas);
  document.body.append(ghost);
  const sky = ui.Constellation(canvas, graph || { nodes: [] }, { seed: tile.dataset.name });
  sky.setSpread(0.9, 1.4);
  const sx = to.width / innerWidth, sy = to.height / innerHeight;
  const a = ui.anim(ghost, ui.reducedMotion() ? [{ opacity: 1 }, { opacity: 0 }] : [
    { transformOrigin: "0 0", transform: "none", borderRadius: "0px" },
    { transformOrigin: "0 0", transform: `translate(${to.left}px,${to.top}px) scale(${sx},${sy})`, borderRadius: "12px" }],
  { duration: ui.reducedMotion() ? 150 : 700, easing: ui.css("ease-standard") || "ease-in", fill: "forwards" });
  ui.settle(a, 1300).then(() => { sky.stop(); ghost.remove(); tile.focus(); });
}

/* The New brain tile turns into a small form in place: name, passphrase twice, colour. */
function newBrainTile(onUnlocked) {
  const wrap = ui.h("div", { class: "new-brain", role: "listitem" });
  const start = ui.ProfileTile({ isNew: true, onCreate: () => { start.replaceWith(form); form.querySelector("input").focus(); } });
  const err = ui.h("p", { class: "eg-profile-err", role: "alert", style: { display: "none" } });
  const colors = ui.h("div", { class: "swatches", role: "radiogroup", "aria-label": "Colour" },
    ...["s0", "s1", "s2"].map((c, i) => ui.h("label", { class: "swatch" },
      ui.h("input", { type: "radio", name: "color", value: c, checked: i === 1 }),
      ui.h("span", { style: { background: colorVar(c) } }), ui.h("span", { class: "eg-sr", text: { s0: "steel", s1: "mint", s2: "violet" }[c] }))));
  const field = (label, attrs) => ui.h("label", { class: "field" }, ui.h("span", { class: "eg-caps", text: label }), ui.h("input", { class: "eg-input", ...attrs }));
  const form = ui.h("form", { class: "eg eg-profile eg-tile eg-ontile new-form", "aria-label": "New brain" },
    ui.h("div", { class: "eg-profile-name", text: "New brain" }),
    ui.h("p", { class: "tile-note", text: "Its own Postgres database, created and migrated now." }),
    field("name", { name: "name", required: true, pattern: "[a-z][a-z0-9_]{0,30}", autocomplete: "off", placeholder: "e.g. meetings", spellcheck: "false" }),
    field("passphrase", { name: "pass", type: "password", required: true, minlength: 8, autocomplete: "new-password" }),
    field("again", { name: "again", type: "password", required: true, minlength: 8, autocomplete: "new-password" }),
    colors, err,
    ui.h("div", { class: "new-actions" }, ui.Button({ label: "Create", type: "submit" }), ui.Button({ label: "Cancel", variant: "secondary", className: "on-tile", onClick: () => form.replaceWith(start) })));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    const show = (m) => { err.style.display = "flex"; err.textContent = m; ui.anim(form, [0, -8, 7, -5, 3, 0].map((x) => ({ transform: `translateX(${x}px)` })), { duration: ui.reducedMotion() ? 1 : 360 }); };
    if (f.get("pass") !== f.get("again")) return show("The two passphrases differ.");
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    btn.textContent = "Creating…";
    try {
      const r = await api("/api/profiles", { name: f.get("name"), passphrase: f.get("pass"), color: f.get("color") });
      const tile = ui.ProfileTile({ name: r.profile.name, color: colorVar(r.profile.color), counts: { items: 0, beliefs: 0, judgements: 0 }, graph: { nodes: [{ id: 0, kind: "person" }], links: [] } });
      form.replaceWith(tile);
      await ui.wait(60);
      await onUnlocked(r.profile, tile);
    } catch (ex) { btn.disabled = false; btn.textContent = "Create"; show(ex.message); }
  });
  wrap.append(start);
  return wrap;
}
