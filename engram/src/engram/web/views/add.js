// Add data: paste text or drop .txt / .md / .eml files. The existing pipeline (POST /api/add, then GET /api/add/<id>)
// runs and the Pipeline tile tells its true story, stage by stage with the server's own timings and words. When an item
// is done it is born into the constellation. The watch's voice notes arrive here too (they are adds from the watch).
import * as ui from "../lib/ui.js";
import { api, every } from "../lib/api.js";
import * as brain from "../lib/brain3d.js";

export function mount(root, ctx) {
  const stops = [];
  const title = ui.h("input", { class: "eg-input", name: "title", placeholder: "Title (optional)", autocomplete: "off" });
  const from = ui.h("input", { class: "eg-input", name: "from", placeholder: "From (optional, e.g. vince.kaminski@enron.com)", autocomplete: "off" });
  const date = ui.h("input", { class: "eg-input", name: "date", type: "date", "aria-label": "Date (optional)" });
  const text = ui.h("textarea", { class: "eg-input", name: "text", rows: "9", placeholder: "Paste an email, a note, meeting minutes…", "aria-label": "Text to add" });
  const picker = ui.h("input", { type: "file", accept: ".txt,.md,.eml,text/plain,message/rfc822", multiple: true, class: "eg-sr", id: "add-files" });
  const drop = ui.h("div", { class: "drop", tabindex: "-1" }, ui.Icon("add"),
    ui.h("span", null, "Drop .txt, .md or .eml files here, or ", ui.h("label", { for: "add-files", class: "link", tabindex: "0", text: "choose files" })), picker);
  const submit = ui.Button({ label: "Add to brain", type: "submit" });
  const form = ui.h("form", { class: "add-form" }, text, ui.h("div", { class: "row3" }, title, from, date), drop, ui.h("div", { class: "row" }, submit, ui.h("span", { class: "hint", text: "Stored and searchable in milliseconds; the models take longer." })));
  const pipe = ui.Pipeline({ title: "Nothing added yet" });
  const recent = ui.h("ol", { class: "recent" });
  root.append(ui.h("section", { class: "view add-view" },
    ui.h("header", { class: "view-head" }, ui.h("div", null, ui.h("p", { class: "eg-caps", text: "unstructured in" }),
      ui.h("h2", { class: "display", text: "Add data" }), ui.h("p", { class: "lead", text: "The agents sort it. Every stage is timed." }))),
    ui.h("div", { class: "add-grid" }, form, ui.h("div", { class: "pipe-col" }, pipe,
      ui.h("section", { class: "panel" }, ui.h("h3", { class: "tagline", text: "Recent additions" }), recent)))));

  /* ------------------------------------------------------------ files */
  const queue = [];
  const label = drop.querySelector("label");
  label.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); picker.click(); } });
  picker.addEventListener("change", () => { readFiles([...picker.files]); picker.value = ""; });
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); readFiles([...e.dataTransfer.files]); });
  async function readFiles(files) {
    for (const f of files) {
      if (!/\.(txt|md|eml)$/i.test(f.name) || f.size > 900_000) { ctx.announce(`${f.name}: only .txt, .md or .eml under 900 KB`); continue; }
      const raw = await f.text();
      queue.push(/\.eml$/i.test(f.name) ? parseEml(raw, f.name) : { title: f.name.replace(/\.(txt|md)$/i, ""), text: raw });
    }
    run();
  }

  /* ------------------------------------------------------------ the run */
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (!text.value.trim()) { text.focus(); return; }
    queue.push({ title: title.value.trim(), from: from.value.trim(), date: date.value, text: text.value });
    text.value = ""; title.value = "";
    run();
  });
  let busy = false;
  async function run() {
    if (busy) return;
    busy = true;
    submit.disabled = true;
    while (queue.length) {
      const body = queue.shift();
      try {
        const { id } = await api("/api/add", { title: body.title || undefined, from: body.from || undefined, date: body.date || undefined, text: body.text });
        await follow(id, body.title || "Note");
      } catch (e) {
        pipe.reset(body.title || "Note");
        pipe.update({ status: "error", stages: [], error: e.message });
      }
      refreshRecent();
    }
    busy = false;
    submit.disabled = false;
  }
  async function follow(id, name) {
    pipe.reset(name);
    for (;;) {
      const st = await api(`/api/add/${id}`);
      await pipe.update(st);
      if (st.status !== "running") {
        if (st.status === "done" && st.graph) {
          const born = brain.merge(st.graph, "born");
          setTimeout(() => brain.mark(born.map((n) => n.id), undefined), 6000);
          ctx.announce(`${name} added as item ${st.item}${st.beliefs.length ? `, ${st.beliefs.length} beliefs` : ""}`);
        }
        return st;
      }
      await ui.wait(250);
    }
  }

  /* ------------------------------------------------------------ recent (the watch's notes appear here too) */
  async function refreshRecent() {
    const list = await api("/api/adds");
    recent.replaceChildren(...(list.length ? list.map((a) => ui.h("li", null, ui.h("button", { type: "button", onClick: () => replay(a) },
      ui.h("span", { class: `dot ${a.status}`, "aria-hidden": "true" }), ui.h("b", { text: a.title }),
      ui.h("span", { class: "meta eg-mono", text: `${a.item ? "item:" + a.item + " · " : ""}${a.status}` })))) : [ui.h("li", { class: "empty", text: "Nothing added in this session yet." })]));
  }
  async function replay(a) {
    const st = await api(`/api/add/${a.id}`);
    pipe.reset(a.title);
    pipe.update(st);
  }
  stops.push(every(5000, refreshRecent));
  return { unmount: () => stops.forEach((s) => s()) };
}

/* A minimal .eml reader: headers (unfolded), the first text/plain part, quoted-printable decoded. */
function parseEml(raw, filename) {
  const [head, ...rest] = raw.replace(/\r\n/g, "\n").split("\n\n");
  const headers = {};
  for (const line of head.replace(/\n[ \t]+/g, " ").split("\n")) {
    const m = /^([\w-]+):\s*(.*)$/.exec(line);
    if (m) headers[m[1].toLowerCase()] = m[2];
  }
  let body = rest.join("\n\n");
  const b = /boundary="?([^";]+)"?/i.exec(headers["content-type"] || "");
  let enc = headers["content-transfer-encoding"] || "";
  if (b) {
    const part = body.split("--" + b[1]).find((p) => /content-type:\s*text\/plain/i.test(p)) || "";
    const [ph, ...pb] = part.replace(/^\n/, "").split("\n\n");
    enc = (/content-transfer-encoding:\s*([\w-]+)/i.exec(ph) || [])[1] || "";
    body = pb.join("\n\n");
  }
  if (/quoted-printable/i.test(enc)) body = body.replace(/=\n/g, "").replace(/=([0-9A-F]{2})/gi, (_, h) => String.fromCharCode(parseInt(h, 16)));
  if (/base64/i.test(enc)) { try { body = atob(body.replace(/\s+/g, "")); } catch { /* keep as is */ } }
  const d = new Date(headers.date || "");
  const from = (/<([^>]+)>/.exec(headers.from || "") || [])[1] || headers.from || "";
  return { title: headers.subject || filename, from, date: isNaN(d) ? "" : d.toISOString().slice(0, 10), text: body.trim() };
}
