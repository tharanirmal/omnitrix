// engram UI kit (ES module): the design system's components as vanilla DOM factories. Each returns an element with
// methods attached. Shared by every view; nothing here talks to the server.
  var SVGNS = "http://www.w3.org/2000/svg";
  var TIERS = ["S0", "S1", "S2", "H"];
  var TIER_NAME = { S0: "code", S1: "small judge", S2: "large model", H: "you" };

  function reduced() { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function css(name, el) { return getComputedStyle(el || document.documentElement).getPropertyValue("--" + name).trim(); }
  function ms(name, fallback) { var v = parseFloat(css(name)); return isNaN(v) ? fallback : v; }
  function h(tag, attrs) {
    var el = document.createElement(tag), i, k, c;
    attrs = attrs || {};
    for (k in attrs) {
      if (!Object.prototype.hasOwnProperty.call(attrs, k) || attrs[k] == null || attrs[k] === false) continue;
      if (k === "class") el.className = attrs[k];
      else if (k === "text") el.textContent = attrs[k];
      else if (k.slice(0, 2) === "on" && typeof attrs[k] === "function") el.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
      else if (k === "style" && typeof attrs[k] === "object") Object.assign(el.style, attrs[k]);
      else el.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    }
    for (i = 2; i < arguments.length; i++) {
      c = arguments[i];
      if (c == null || c === false) continue;
      if (Array.isArray(c)) c.forEach(function (x) { if (x != null && x !== false) el.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
      else el.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
    }
    return el;
  }
  function s(tag, attrs) {
    var el = document.createElementNS(SVGNS, tag), k;
    for (k in attrs || {}) if (attrs[k] != null) el.setAttribute(k, attrs[k]);
    for (var i = 2; i < arguments.length; i++) if (arguments[i]) el.appendChild(arguments[i]);
    return el;
  }
  function fmt(n) { return typeof n === "number" ? n.toLocaleString("en-US") : String(n == null ? "—" : n); }
  function seeded(str) { var x = 2166136261; for (var i = 0; i < str.length; i++) { x ^= str.charCodeAt(i); x = Math.imul(x, 16777619); } return function () { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; return ((x >>> 0) % 100000) / 100000; }; }
  function anim(el, frames, opts) { if (!el.animate) return { finished: Promise.resolve() }; return el.animate(frames, opts); }
  /* A model spec as a short name: "mlx:data/models/judge-v1-q4;remember,meeting_request=mlx:…/judge-v2-q4" (a judge
     routed per decision) reads "judge-v1-q4 + judge-v2-q4"; "qwen3:14b" stays as it is. */
  function shortModel(spec) {
    return String(spec || "").split(";").map(function (part) {
      var m = part.slice(part.indexOf("=") + 1);
      return m.indexOf("/") >= 0 ? m.slice(m.lastIndexOf("/") + 1) : m;
    }).join(" + ");
  }
  function wait(t) { return new Promise(function (r) { setTimeout(r, t); }); }
  /* An animation's end, or its planned end plus a margin, whichever comes first: a browser may pause animations (a
     background tab, a hidden pane, power saving), and nothing the page needs to go on may wait on one. */
  function settle(a, ms) {
    return Promise.race([a.finished.catch(function () {}), wait(ms).then(function () { try { a.finish(); } catch (e) { /* already gone */ } })]);
  }
  function tierColor(t, el) { return css({ S0: "tier-s0", S1: "tier-s1", S2: "tier-s2", H: "tier-h" }[t] || "on-tile", el); }

  /* ---------------------------------------------------------------- Icon: one 1.5px stroke family, 24 grid */
  var ICONS = {
    agents: "M5 6.5a1.5 1.5 0 1 0 0-.01M12 12a1.5 1.5 0 1 0 0-.01M19 6.5a1.5 1.5 0 1 0 0-.01M19 17.5a1.5 1.5 0 1 0 0-.01M6.3 7.4l4.4 3.7M13.3 11.1l4.4-3.7M13.3 12.9l4.4 3.7",
    database: "M4.5 6c0-1.4 3.4-2.5 7.5-2.5s7.5 1.1 7.5 2.5-3.4 2.5-7.5 2.5S4.5 7.4 4.5 6zM4.5 6v12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5V6M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5",
    add: "M4 13.5v4A2.5 2.5 0 0 0 6.5 20h11a2.5 2.5 0 0 0 2.5-2.5v-4M12 4v11M7.5 10.5 12 15l4.5-4.5",
    ledger: "M9.5 14.5l5-5M10.8 6.9l1.4-1.4a3.5 3.5 0 0 1 5 5l-1.4 1.4M13.2 17.1l-1.4 1.4a3.5 3.5 0 0 1-5-5l1.4-1.4",
    lock: "M6.5 10.5h11v9h-11zM8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5M12 14v2",
    watch: "M8 6.5h8a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H8A1.5 1.5 0 0 1 6.5 16V8A1.5 1.5 0 0 1 8 6.5zM9 6.5 9.8 3h4.4l.8 3.5M9 17.5l.8 3.5h4.4l.8-3.5M12 9.5V12l1.5 1",
    check: "M5 12.5l4.5 4.5L19 7.5",
    x: "M6.5 6.5l11 11M17.5 6.5l-11 11",
    chevron: "M9.5 6l6 6-6 6",
    search: "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM15.2 15.2 20 20",
    command: "M9 9V6.5A2.5 2.5 0 1 0 6.5 9H9zm0 0h6M9 9v6m6-6V6.5A2.5 2.5 0 1 1 17.5 9H15zm0 0v6m0 0h2.5a2.5 2.5 0 1 1-2.5 2.5V15zm0 0H9m0 0v2.5A2.5 2.5 0 1 1 6.5 15H9z",
    gate: "M5 20V6M19 20V6M5 9h14M3.5 20h17",
    note: "M7 3.5h7l4 4v13H7zM14 3.5v4h4M9.5 12h6M9.5 15h6M9.5 18h3.5",
    constellation: "M5 17a1.2 1.2 0 1 0 0-.01M9 7a1.2 1.2 0 1 0 0-.01M15.5 10a1.2 1.2 0 1 0 0-.01M19 4.5a1.2 1.2 0 1 0 0-.01M18 18.5a1.2 1.2 0 1 0 0-.01M5.6 15.9l2.8-7.8M10.1 7.5l4.3 2M16.4 9.1l2-3.6M15.9 11.1l1.6 6.2",
    timeline: "M4 19.5h16M4 4.5v15M7.5 8h7M10 12h8M7.5 16h5",
    table: "M4 5.5h16v13H4zM4 10h16M4 14.5h16M10 5.5v13",
    verify: "M12 3.5 19 6v5.5c0 4.3-3 7.6-7 9-4-1.4-7-4.7-7-9V6zM8.8 12l2.2 2.2 4.4-4.4",
    export: "M12 15V4M7.5 8.5 12 4l4.5 4.5M5 13.5v4A2.5 2.5 0 0 0 7.5 20h9a2.5 2.5 0 0 0 2.5-2.5v-4",
    pulse: "M3 12h4l2-5 4 10 2-5h6",
    clock: "M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17zM12 7.5V12l3 2",
    person: "M12 11.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5",
    plus: "M12 5v14M5 12h14",
    alert: "M12 4 21 19.5H3zM12 10v4.5M12 17v.5"
  };
  function Icon(name, opts) {
    opts = opts || {};
    var svg = s("svg", { viewBox: "0 0 24 24", class: "eg-icon" + (opts.size === "sm" ? " sm" : ""), "aria-hidden": opts.label ? null : "true", role: opts.label ? "img" : null, "aria-label": opts.label || null });
    svg.appendChild(s("path", { d: ICONS[name] || ICONS.plus }));
    return svg;
  }
  Icon.names = Object.keys(ICONS);
  Icon.paths = ICONS;

  /* ---------------------------------------------------------------- Button */
  function Button(p) {
    p = p || {};
    var b = h("button", { type: p.type || "button", class: "eg-btn eg-btn--" + (p.variant || "primary") + (p.className ? " " + p.className : ""), disabled: p.disabled, "aria-label": p.ariaLabel, onClick: p.onClick },
      p.icon ? Icon(p.icon, { size: "sm" }) : null, p.label ? h("span", { text: p.label }) : null, p.kbd ? h("span", { class: "eg-kbd", text: p.kbd }) : null);
    return b;
  }

  /* ---------------------------------------------------------------- TierChip */
  function TierChip(p) {
    p = typeof p === "string" ? { tier: p } : (p || {});
    var t = TIERS.indexOf(p.tier) >= 0 ? p.tier : "S0";
    var el = h("span", { class: "eg-chip eg-chip--" + t + (p.onTile ? " on-tile" : ""), "data-live": p.live ? "true" : null, title: t + " · " + TIER_NAME[t] },
      h("span", { class: "eg-dot", "aria-hidden": "true" }), h("span", { text: p.label || t }), p.model ? h("span", { class: "eg-chip-model", text: p.model }) : null);
    el.setLive = function (on) { el.setAttribute("data-live", on ? "true" : "false"); };
    return el;
  }

  /* ---------------------------------------------------------------- Readout: tabular numerals whose changed digits roll in */
  function Readout(p) {
    p = p || {};
    var digits = h("span", { class: "eg-digits", "aria-hidden": "true" });
    var sr = h("span", { class: "eg-sr", "aria-live": p.live ? "polite" : null });
    var el = h("span", { class: "eg-readout" + (p.size ? " " + p.size : "") },
      p.label ? h("span", { class: "eg-caps", text: p.label }) : null,
      h("span", { class: "eg-readout-val" }, digits, p.unit ? h("span", { class: "eg-readout-unit", text: p.unit }) : null, sr));
    var prev = "";
    function render(v) {
      var str = p.format ? p.format(v) : fmt(v);
      var pad = prev.length === str.length ? prev : "";
      digits.textContent = "";
      for (var i = 0; i < str.length; i++) {
        var d = h("span", { class: "eg-digit", text: str[i] });
        if (prev && pad[i] !== str[i]) { d.classList.add("roll"); d.style.animationDelay = (i * 18) + "ms"; }
        digits.appendChild(d);
      }
      sr.textContent = (p.label ? p.label + " " : "") + str + (p.unit ? " " + p.unit : "");
      prev = str;
    }
    render(p.value);
    el.set = function (v) { render(v); return el; };
    return el;
  }

  /* ---------------------------------------------------------------- TopBar */
  function TopBar(p) {
    p = p || {};
    var counts = p.counts || {};
    var r = {
      items: Readout({ label: "items", value: counts.items, size: "sm", live: true }),
      beliefs: Readout({ label: "beliefs", value: counts.beliefs, size: "sm", live: true }),
      judgements: Readout({ label: "judgements", value: counts.judgements, size: "sm", live: true })
    };
    var pend = h("button", { class: "eg-pending", type: "button", "data-count": String(p.pending || 0), onClick: function () { p.onPending && p.onPending(); } },
      h("span", { class: "eg-dot", "aria-hidden": "true" }), h("span", { class: "lbl" }));
    function setPending(n) {
      pend.setAttribute("data-count", String(n));
      pend.querySelector(".lbl").textContent = n ? n + " waiting" : "0 waiting";
      pend.setAttribute("aria-label", n ? n + " approvals waiting on you. Open approval card." : "No approvals waiting");
      if (n && !reduced()) anim(pend, [{ transform: "scale(1)" }, { transform: "scale(1.08)" }, { transform: "scale(1)" }], { duration: 320, easing: css("ease-spring") || "ease-out" });
    }
    var bar = h("header", { class: "eg eg-topbar eg-ontile", role: "banner" },
      h("div", { class: "eg-topbar-brand" }, h("span", { text: "engram" }), h("span", { class: "sep", text: "/" }),
        h("span", { class: "eg-avatar", style: { background: p.color || css("tier-s1") }, text: (p.brain || "?").charAt(0).toUpperCase(), "aria-hidden": "true" }),
        h("span", { text: p.brain || "" })),
      h("div", { class: "eg-topbar-counts" }, r.items, r.beliefs, r.judgements),
      h("div", { class: "eg-topbar-spacer" }),
      h("div", { class: "eg-topbar-models" },
        TierChip({ tier: "S1", model: p.s1 || "…", onTile: true }), TierChip({ tier: "S2", model: p.s2 || "…", onTile: true })),
      h("span", { class: "eg-seal", title: "Served on 127.0.0.1. Nothing is loaded from or sent to the network." }, Icon("lock", { size: "sm" }), h("span", { class: "eg-caps", text: "local only" })),
      pend,
      h("button", { class: "eg-kbdbtn", type: "button", "aria-label": "Search everything (Command K)", onClick: function () { p.onCommand && p.onCommand(); } }, Icon("search", { size: "sm" }), h("span", { class: "eg-kbd", text: "⌘K" })));
    setPending(p.pending || 0);
    bar.setCounts = function (c) { Object.keys(c).forEach(function (k) { if (r[k] && c[k] != null) r[k].set(c[k]); }); };
    bar.setModels = function (s1, s2) {
      var m = bar.querySelector(".eg-topbar-models"); m.textContent = "";
      m.append(TierChip({ tier: "S1", model: shortModel(s1), onTile: true }), TierChip({ tier: "S2", model: shortModel(s2), onTile: true }));
      m.title = "S1 " + s1 + "\nS2 " + s2;                  // the full spec, e.g. which decisions go to which judge
    };
    bar.setPending = setPending;
    return bar;
  }

  /* A View Transition around `swap`, or just `swap` when there is none to see (reduced motion, a hidden tab). A
     transition the browser skips rejects its `ready` promise; that is not an error. */
  function transition(swap) {
    if (!document.startViewTransition || reduced() || document.hidden) { swap(); return; }
    document.startViewTransition(swap).ready.catch(function () {});
  }

  /* ---------------------------------------------------------------- Segmented: lens switch with a sliding thumb and a View Transition */
  function Segmented(p) {
    p = p || {};
    var opts = p.options || [];
    var value = p.value || (opts[0] && opts[0].value);
    var thumb = h("span", { class: "eg-seg-thumb", "aria-hidden": "true" });
    var el = h("div", { class: "eg eg-seg", role: "radiogroup", "aria-label": p.label || "View" }, thumb);
    var btns = opts.map(function (o) {
      var b = h("button", { type: "button", role: "radio", "aria-checked": String(o.value === value), tabindex: o.value === value ? "0" : "-1",
        onClick: function () { select(o.value, true); } }, o.icon ? Icon(o.icon, { size: "sm" }) : null, h("span", { text: o.label }));
      b._v = o.value; el.appendChild(b); return b;
    });
    el.addEventListener("keydown", function (e) {
      var i = btns.findIndex(function (b) { return b._v === value; });
      if (e.key === "ArrowRight" || e.key === "ArrowDown") i = (i + 1) % btns.length; else if (e.key === "ArrowLeft" || e.key === "ArrowUp") i = (i - 1 + btns.length) % btns.length; else return;
      e.preventDefault(); select(btns[i]._v, true); btns[i].focus();
    });
    function place() {
      var b = btns.find(function (x) { return x._v === value; }); if (!b) return;
      thumb.style.width = b.offsetWidth + "px"; thumb.style.transform = "translateX(" + (b.offsetLeft - 3) + "px)";
    }
    function select(v, user) {
      if (v === value) return;
      value = v;
      btns.forEach(function (b) { var on = b._v === v; b.setAttribute("aria-checked", String(on)); b.tabIndex = on ? 0 : -1; });
      place();
      if (user && p.onChange) {
        transition(function () { p.onChange(v); });
      }
    }
    requestAnimationFrame(place);
    if (window.ResizeObserver) new ResizeObserver(place).observe(el);
    el.select = function (v) { select(v, false); };
    Object.defineProperty(el, "value", { get: function () { return value; } });
    return el;
  }

  /* ---------------------------------------------------------------- Constellation (canvas): a brain's own graph sample, drifting */
  var SHAPES = { person: "circle", item: "dot", commitment: "ring", decision: "diamond", meeting: "square" };
  function Constellation(canvas, graph, opts) {
    opts = opts || {};
    var ctx = canvas.getContext("2d"), rnd = seeded(opts.seed || "engram");
    var nodes = (graph.nodes || []).map(function (n) {
      var x = rnd(), y = rnd();
      return { id: n.id, kind: n.kind || "item", hot: !!n.hot, ox: x, oy: y, x: x, y: y, vx: 0, vy: 0, ph: rnd() * 6.28 };
    });
    var byId = {}; nodes.forEach(function (n) { byId[n.id] = n; });
    var links = (graph.links || []).map(function (l) { return [byId[l[0]], byId[l[1]]]; }).filter(function (l) { return l[0] && l[1]; });
    var raf = 0, t0 = performance.now(), scale = 1, spread = 1;
    function size() { var r = canvas.getBoundingClientRect(), d = window.devicePixelRatio || 1; canvas.width = Math.max(1, r.width * d); canvas.height = Math.max(1, r.height * d); ctx.setTransform(d, 0, 0, d, 0, 0); return r; }
    var box = size();
    function draw(now) {
      var W = box.width, H = box.height, t = (now - t0) / 1000, m = reduced() ? 0 : 1;
      ctx.clearRect(0, 0, W, H);
      var ink = css("on-tile", canvas) || "#ECE8DF", mute = css("on-tile-muted", canvas) || "#9A9689", hot = css("link-on-tile", canvas) || "#ECE8DF";
      var pad = 14, cx = W / 2, cy = H / 2;
      nodes.forEach(function (n) {
        n.x = n.ox + m * 0.012 * Math.sin(t * 0.35 + n.ph); n.y = n.oy + m * 0.012 * Math.cos(t * 0.29 + n.ph * 1.3);
        n.px = cx + (pad + n.x * (W - 2 * pad) - cx) * spread; n.py = cy + (pad + n.y * (H - 2 * pad) - cy) * spread;
      });
      ctx.lineWidth = 1; ctx.strokeStyle = mute; ctx.globalAlpha = 0.28;
      links.forEach(function (l) { ctx.beginPath(); ctx.moveTo(l[0].px, l[0].py); ctx.lineTo(l[1].px, l[1].py); ctx.stroke(); });
      ctx.globalAlpha = 1;
      nodes.forEach(function (n) {
        var c = n.hot ? hot : (n.kind === "item" ? mute : ink), r = (n.kind === "person" ? 2.6 : n.kind === "item" ? 1.3 : 2.3) * scale;
        ctx.fillStyle = c; ctx.strokeStyle = c; ctx.lineWidth = 1.2;
        var sh = SHAPES[n.kind] || "dot";
        ctx.beginPath();
        if (sh === "ring") { ctx.arc(n.px, n.py, r + 0.6, 0, 6.283); ctx.stroke(); }
        else if (sh === "diamond") { ctx.moveTo(n.px, n.py - r - 0.8); ctx.lineTo(n.px + r + 0.8, n.py); ctx.lineTo(n.px, n.py + r + 0.8); ctx.lineTo(n.px - r - 0.8, n.py); ctx.closePath(); ctx.fill(); }
        else if (sh === "square") { ctx.rect(n.px - r, n.py - r, r * 2, r * 2); ctx.fill(); }
        else { ctx.arc(n.px, n.py, r, 0, 6.283); ctx.fill(); }
        if (n.hot && m) { ctx.globalAlpha = 0.25 + 0.2 * Math.sin(t * 3); ctx.beginPath(); ctx.arc(n.px, n.py, r + 5, 0, 6.283); ctx.stroke(); ctx.globalAlpha = 1; }
      });
      if (!reduced()) raf = requestAnimationFrame(draw);
    }
    raf = requestAnimationFrame(draw);
    if (window.ResizeObserver) new ResizeObserver(function () { box = size(); if (reduced()) draw(performance.now()); }).observe(canvas);
    return {
      stop: function () { cancelAnimationFrame(raf); },
      setSpread: function (v, sc) { spread = v; scale = sc || 1; if (reduced()) draw(performance.now()); },
      highlight: function (ids) { var set = {}; (ids || []).forEach(function (i) { set[i] = 1; }); nodes.forEach(function (n) { n.hot = !!set[n.id]; }); if (reduced()) draw(performance.now()); },
      redraw: function () { box = size(); draw(performance.now()); }
    };
  }

  /* ---------------------------------------------------------------- ProfileTile: pick a brain, unlock it, expand into the dashboard */
  function ProfileTile(p) {
    p = p || {};
    if (p.isNew) {
      var nb = h("button", { class: "eg eg-profile eg-profile-new eg-tile", type: "button", onClick: function () { p.onCreate && p.onCreate(); }, style: { background: "transparent", color: "inherit" } },
        h("span", { class: "ring" }, Icon("plus")), h("span", { class: "eg-profile-name", style: { justifyContent: "center" }, text: "New brain" }),
        h("span", { class: "eg-caps", text: "its own Postgres database" }));
      return nb;
    }
    var c = p.counts || {};
    var canvas = h("canvas", { "aria-hidden": "true" });
    var input = h("input", { class: "eg-input", type: "password", autocomplete: "current-password", placeholder: "Passphrase", "aria-label": "Passphrase for " + p.name });
    var err = h("div", { class: "eg-profile-err", role: "alert" }, Icon("alert", { size: "sm" }), h("span"));
    var unlockBtn = Button({ label: "Unlock", type: "submit" });
    var form = h("form", { onSubmit: function (e) { e.preventDefault(); if (p.onUnlock) p.onUnlock(input.value, el); } }, input, unlockBtn);
    var el = h("div", { class: "eg eg-profile eg-tile eg-ontile", "data-name": p.name, tabindex: "0", role: "button", "aria-expanded": "false", "aria-label": "Brain " + p.name + ". Press Enter to unlock." },
      h("div", { class: "eg-profile-sky" }, canvas),
      h("div", { class: "eg-profile-name" }, h("span", { class: "eg-avatar", style: { background: p.color || css("tier-s1"), width: "22px", height: "22px", fontSize: "12px" }, text: (p.name || "?").charAt(0).toUpperCase() }), h("span", { text: p.name })),
      h("div", { class: "eg-profile-counts" },
        Readout({ label: "items", value: c.items, size: "sm" }), Readout({ label: "beliefs", value: c.beliefs, size: "sm" }), Readout({ label: "judgements", value: c.judgements, size: "sm" })),
      h("div", { class: "eg-profile-pass" }, h("div", null, form, err)));
    var sky;
    requestAnimationFrame(function () { sky = Constellation(canvas, p.graph || { nodes: [] }, { seed: p.name }); el._sky = sky; });
    function focus() {
      if (el.classList.contains("is-focused")) return;
      el.classList.add("is-focused"); el.setAttribute("aria-expanded", "true");
      setTimeout(function () { input.focus(); }, reduced() ? 0 : ms("dur-ui", 240));
      p.onFocus && p.onFocus(el);
    }
    el.addEventListener("click", function (e) { if (!form.contains(e.target)) focus(); });
    el.addEventListener("keydown", function (e) { if ((e.key === "Enter" || e.key === " ") && e.target === el) { e.preventDefault(); focus(); } if (e.key === "Escape") el.blur_(); });
    el.blur_ = function () { el.classList.remove("is-focused", "has-error"); el.setAttribute("aria-expanded", "false"); input.value = ""; el.focus(); };
    el.focusTile = focus;
    el.reject = function (msg) {
      el.classList.add("has-error"); err.lastChild.textContent = msg || "That passphrase doesn't open this brain.";
      input.select();
      if (reduced()) return anim(el, [{ opacity: 0.6 }, { opacity: 1 }], { duration: 160 }).finished;
      return anim(el, [0, -9, 8, -6, 5, -3, 2, 0].map(function (x) { return { transform: "translateX(" + x + "px)" }; }), { duration: 380, easing: "cubic-bezier(.36,.07,.19,.97)" }).finished;
    };
    /* the signature moment: the tile's constellation grows into the full-screen brain. target: an element (or the viewport). */
    el.expand = function (target) {
      var from = canvas.getBoundingClientRect();
      var to = target ? target.getBoundingClientRect() : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
      var ghost = h("div", { class: "eg-expand", style: { left: to.left + "px", top: to.top + "px", width: to.width + "px", height: to.height + "px" } });
      var gc = h("canvas"); ghost.appendChild(gc); document.body.appendChild(ghost);
      var big = Constellation(gc, p.graph || { nodes: [] }, { seed: p.name });
      var sx = from.width / to.width, sy = from.height / to.height, dx = from.left - to.left, dy = from.top - to.top;
      var dur = reduced() ? 1 : ms("dur-physics", 1600) * 0.55;
      big.setSpread(0.9, 1.4);
      var a = anim(ghost, reduced() ? [{ opacity: 0 }, { opacity: 1 }] :
        [{ transformOrigin: "0 0", transform: "translate(" + dx + "px," + dy + "px) scale(" + sx + "," + sy + ")", borderRadius: "12px" },
         { transformOrigin: "0 0", transform: "none", borderRadius: "0px" }],
        { duration: reduced() ? 150 : dur, easing: css("ease-standard") || "ease-out", fill: "forwards" });
      return settle(a, (reduced() ? 150 : dur) + 600).then(function () { return { ghost: ghost, constellation: big, collapse: function () {
        var back = anim(ghost, reduced() ? [{ opacity: 1 }, { opacity: 0 }] :
          [{ transformOrigin: "0 0", transform: "none" }, { transformOrigin: "0 0", transform: "translate(" + dx + "px," + dy + "px) scale(" + sx + "," + sy + ")", borderRadius: "12px" }],
          { duration: reduced() ? 150 : dur * 0.8, easing: css("ease-standard") || "ease-in", fill: "forwards" });
        return settle(back, (reduced() ? 150 : dur * 0.8) + 600).then(function () { big.stop(); ghost.remove(); el.blur_(); });
      } }; });
    };
    return el;
  }

  /* ---------------------------------------------------------------- Switchboard: S0 → S1 → S2 → H lanes; particles trace each decision's real path */
  var STATUS_LABEL = { idle: "idle", running: "running", waiting: "waiting on you", offline: "offline", error: "error" };
  function Switchboard(p) {
    p = p || {};
    var lanes = {}, nodes = {}, only = null;             // only: the roster role picked in the filter, or none
    var layer = h("div", { class: "eg-particles", "aria-hidden": "true" });
    var live = h("div", { class: "eg-sr", "aria-live": "polite" });
    var grid = h("div", { class: "eg-board-lanes" });
    var heads = p.lanes || { S0: "code", S1: "small judge", S2: "large model", H: "you" };
    TIERS.forEach(function (t) {
      lanes[t] = h("section", { class: "eg-lane", "data-tier": t, "aria-label": t + " " + heads[t] },
        h("div", { class: "eg-lane-head" }, h("span", { class: "t", text: t + " · " + heads[t] }), h("span", { class: "m", text: (p.laneMeta && p.laneMeta[t]) || "" })));
      grid.appendChild(lanes[t]);
    });
    var foot = h("div", { class: "eg-board-foot" });
    var el = h("div", { class: "eg eg-board eg-tile eg-ontile" }, grid, layer, foot, live);
    function nodeFor(a) {
      var status = a.status || "idle";
      var b = h("button", { type: "button", class: "eg-agent" + (a.device ? " is-device" : "") + (only && a.role !== only ? " dim" : ""), "data-tier": a.tier, "data-status": status,
        "data-role": a.role || null,
        "aria-label": (a.role ? a.role + ": " : "") + a.name + ", " + (STATUS_LABEL[status] || status) + (a.task ? ", " + a.task : ""), title: a.task || null,
        onClick: function () { p.onSelect && p.onSelect(b._a, b); } },
        a.device ? Icon("watch", { size: "sm" }) : h("span", { class: "eg-dot", "aria-hidden": "true" }),
        h("span", { class: "n" }, a.role ? h("span", { class: "role", text: a.role }) : null, a.name),
        h("span", { class: "meta" }, h("span", { class: "st", text: STATUS_LABEL[status] || status }), h("span", { class: "mdl", text: shortModel(a.model) || a.task || "", title: a.model || null })),
        a.pending ? h("span", { class: "badge", text: String(a.pending), "aria-hidden": "true" }) : null);
      b._a = a; return b;
    }
    (p.agents || []).forEach(function (a) { var n = nodeFor(a); nodes[a.id] = n; (lanes[a.tier] || lanes.S0).appendChild(n); });
    el.setFoot = function (items) { foot.textContent = ""; (items || []).forEach(function (it) { foot.appendChild(h("span", null, it[0] + " ", h("span", { class: "eg-num", text: it[1] }))); }); };
    if (p.foot) el.setFoot(p.foot);
    el.setStatus = function (id, status, extra) {
      var n = nodes[id]; if (!n) return; var a = Object.assign({}, n._a, extra || {}, { status: status });
      var m = nodeFor(a); n.replaceWith(m); nodes[id] = m;
      live.textContent = a.name + " is " + (STATUS_LABEL[status] || status);
    };
    el.update = function (agents) {
      (agents || []).forEach(function (a) {
        var n = nodes[a.id];
        if (!n) { n = nodeFor(a); nodes[a.id] = n; (lanes[a.tier] || lanes.S0).appendChild(n); return; }
        var o = n._a;
        if (o.status !== a.status || o.model !== a.model || (o.pending || 0) !== (a.pending || 0) || o.name !== a.name || o.task !== a.task || o.role !== a.role) {
          var m = nodeFor(a); var had = document.activeElement === n; n.replaceWith(m); nodes[a.id] = m; if (had) m.focus();
          if (o.status !== a.status) live.textContent = a.name + " is " + (STATUS_LABEL[a.status] || a.status);
        } else n._a = a;
      });
    };
    /* Light one roster role's cards across the tier lanes (the others dim); null shows them all. */
    el.filter = function (role) {
      only = role || null;
      Object.keys(nodes).forEach(function (id) { var n = nodes[id]; n.classList.toggle("dim", !!only && n._a.role !== only); });
    };
    el.flash = function (id) { var n = nodes[id]; if (!n) return; n.classList.remove("flash"); void n.offsetWidth; n.classList.add("flash"); };
    function center(n) { var r = n.getBoundingClientRect(), o = el.getBoundingClientRect(); return { x: r.left - o.left + r.width / 2, y: r.top - o.top + r.height / 2 }; }
    function hopDuration(t) { return { S0: 180, S1: 320, S2: ms("dur-s2", 900), H: 700 }[t] || 400; }
    /* path: agent ids in the order the decision actually travelled, e.g. ["gate","judge","ask"]; the last one settled it. */
    el.fire = function (path, opts) {
      opts = opts || {};
      var ns = path.map(function (id) { return nodes[id]; }).filter(Boolean); if (!ns.length) return Promise.resolve();
      var last = ns[ns.length - 1];
      live.textContent = opts.say || ("Decision settled by " + last._a.name + " (" + last._a.tier + ")");
      if (reduced()) { last.classList.remove("decided"); void last.offsetWidth; last.classList.add("decided"); return Promise.resolve(); }
      var dot = h("span", { class: "eg-particle" }); layer.appendChild(dot);
      var chain = Promise.resolve();
      ns.forEach(function (n, i) {
        chain = chain.then(function () {
          var t = n._a.tier; dot.setAttribute("data-tier", t); dot.style.setProperty("--c", tierColor(t, el));
          var to = center(n);
          if (i === 0) { dot.style.left = to.x + "px"; dot.style.top = to.y + "px"; return anim(dot, [{ opacity: 0, transform: "scale(.2)" }, { opacity: 1, transform: "scale(1)" }], { duration: 120 }).finished; }
          var from = center(ns[i - 1]);
          var easing = t === "S0" ? "steps(4, end)" : t === "S2" ? (css("ease-s2") || "ease-in-out") : "cubic-bezier(.2,.8,.2,1)";
          var mid = { x: (from.x + to.x) / 2, y: Math.min(from.y, to.y) - 24 };
          return anim(dot, [{ left: from.x + "px", top: from.y + "px" }, { left: mid.x + "px", top: mid.y + "px", offset: .5 }, { left: to.x + "px", top: to.y + "px" }], { duration: hopDuration(t), easing: easing, fill: "forwards" }).finished
            .then(function () {
              dot.style.left = to.x + "px"; dot.style.top = to.y + "px";
              n.classList.remove("decided"); void n.offsetWidth; n.classList.add("decided");
              if (t === "S1" && i < ns.length - 1) return anim(dot, [{ opacity: 1 }, { opacity: .2 }, { opacity: 1 }, { opacity: .3 }, { opacity: 1 }], { duration: 160 }).finished;
            });
        });
      });
      return chain.then(function () {
        var to = center(last), ring = h("span", { class: "eg-ring", style: { left: to.x + "px", top: to.y + "px" } });
        ring.style.setProperty("--c", tierColor(last._a.tier, el)); layer.appendChild(ring);
        anim(dot, [{ opacity: 1 }, { opacity: 0 }], { duration: 200, fill: "forwards" }).finished.then(function () { dot.remove(); });
        return anim(ring, [{ transform: "scale(1)", opacity: 1 }, { transform: "scale(5)", opacity: 0 }], { duration: 520, easing: "ease-out" }).finished.then(function () { ring.remove(); });
      });
    };
    el.node = function (id) { return nodes[id]; };
    return el;
  }

  /* ---------------------------------------------------------------- Sparkline */
  function Sparkline(p) {
    p = p || {};
    var v = p.values || [], W = p.width || 300, H = p.height || 56, pad = 4;
    var max = Math.max.apply(null, v.concat([1])), min = 0;
    var X = function (i) { return pad + (i / Math.max(1, v.length - 1)) * (W - 2 * pad - 40); };
    var Y = function (x) { return H - pad - ((x - min) / (max - min || 1)) * (H - 2 * pad); };
    var sorted = v.slice().sort(function (a, b) { return a - b; });
    var q = function (f) { return sorted.length ? sorted[Math.min(sorted.length - 1, Math.floor(f * sorted.length))] : 0; };
    var p50 = q(0.5), p95 = q(0.95);
    var svg = s("svg", { class: "eg-spark", viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none", role: "img", "aria-label": (p.label || "latency") + ": p50 " + Math.round(p50) + " ms, p95 " + Math.round(p95) + " ms over " + v.length + " decisions" });
    svg.style.setProperty("--c", tierColor(p.tier || "S1", document.documentElement));
    [["p95", p95], ["p50", p50]].forEach(function (r) {
      svg.appendChild(s("line", { class: "ref", x1: pad, x2: W - 40, y1: Y(r[1]), y2: Y(r[1]) }));
      var t = s("text", { class: "lbl", x: W - 36, y: Y(r[1]) + 3 }); t.textContent = r[0] + " " + Math.round(r[1]); svg.appendChild(t);
    });
    var d = v.map(function (x, i) { return (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(x).toFixed(1); }).join(" ");
    var ln = s("path", { class: "ln", d: d }); svg.appendChild(ln);
    if (v.length) svg.appendChild(s("circle", { class: "pt", cx: X(v.length - 1), cy: Y(v[v.length - 1]), r: 2.5 }));
    if (!reduced()) requestAnimationFrame(function () {
      var L = ln.getTotalLength ? ln.getTotalLength() : 0; if (!L) return;
      ln.style.strokeDasharray = L; anim(ln, [{ strokeDashoffset: L }, { strokeDashoffset: 0 }], { duration: 700, easing: "cubic-bezier(.2,.8,.2,1)" });
    });
    return svg;
  }

  /* ---------------------------------------------------------------- AgentDrawer */
  function AgentDrawer(p) {
    p = p || {};
    var a = p.agent || {};
    var list = h("ul", { class: "eg-dlist" });
    (p.decisions || []).forEach(function (d) {
      list.appendChild(h("li", null, h("span", { text: d.question + " → " + d.value }), TierChip({ tier: d.tier, onTile: true }), h("span", { class: "eg-num", text: d.latency_ms + " ms" }),
        h("span", { class: "sub", text: d.subject + " · p " + d.p.toFixed(2) + (d.settled ? " · settled" : " · escalated") })));
    });
    var el = h("aside", { class: "eg eg-drawer eg-tile eg-ontile", "aria-label": a.name + " details" },
      h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" } },
        h("div", null, h("span", { class: "eg-caps", text: a.tier + " · " + (TIER_NAME[a.tier] || "") }), h("h3", { text: a.name })),
        p.onClose ? Button({ variant: "icon", icon: "x", ariaLabel: "Close", onClick: p.onClose }) : null),
      a.model ? h("div", null, TierChip({ tier: a.tier, model: a.model, onTile: true, live: a.status === "running" || a.status === "waiting" })) : null,
      h("div", { class: "eg-drawer-stats" },
        Readout({ label: "p50", value: a.p50, unit: "ms" }), Readout({ label: "p95", value: a.p95, unit: "ms" }), Readout({ label: "today", value: a.today })),
      h("div", null, h("span", { class: "eg-caps", text: "latency · last " + (p.latencies || []).length + " ledger rows" }), Sparkline({ values: p.latencies || [], tier: a.tier })),
      h("div", null, h("span", { class: "eg-caps", text: "recent decisions" }), list),
      a.status === "waiting" ? h("div", { class: "eg-drawer-actions" },
        Button({ label: "Approve", icon: "check", onClick: p.onApprove }), Button({ label: "Deny", variant: "secondary", className: "on-tile", onClick: p.onDeny })) : null);
    return el;
  }

  /* ---------------------------------------------------------------- Pipeline: the true story of /api/add, stage by stage */
  var STAGES = [["stored", "database"], ["embedded", "constellation"], ["gate", "gate"], ["extracted", "timeline"], ["vault", "note"]];
  function Pipeline(p) {
    p = p || {};
    var fill = h("i");
    var rail = h("div", { class: "eg-pipe-rail" }, h("div", { class: "eg-pipe-line", "aria-hidden": "true" }, fill));
    var st = {};
    STAGES.forEach(function (x) {
      var node = h("div", { class: "eg-stage-node" }, Icon(x[1], { size: "sm" }));
      var ms_ = h("div", { class: "ms" }), dt = h("div", { class: "dt" }), vis = h("div", { class: "eg-stage-vis", "aria-hidden": "true" });
      var col = h("div", { class: "eg-stage", "data-state": "idle", role: "listitem" }, node, h("span", { class: "eg-caps", text: x[0] }), ms_, dt, vis);
      st[x[0]] = { col: col, ms: ms_, dt: dt, vis: vis }; rail.appendChild(col);
    });
    rail.setAttribute("role", "list");
    var title = h("span", { class: "ttl", text: p.title || "Note" }), total = h("span", { class: "eg-pipe-total" });
    var errBox = h("div", { class: "eg-pipe-err", role: "alert" }, Icon("alert", { size: "sm" }), h("span"));
    var foot = h("div", { class: "eg-pipe-foot", "aria-live": "polite" });
    var el = h("div", { class: "eg eg-pipe eg-tile eg-ontile" }, h("div", { class: "eg-pipe-head" }, title, total), rail, errBox, foot);
    var shown = 0, queue = Promise.resolve(), sum = 0, bins;

    function progress(i) { var f = i / (STAGES.length - 1); fill.style.transform = window.innerWidth <= 720 ? "scaleY(" + f + ")" : "scaleX(" + f + ")"; }
    function visStored(v, n) {
      var box = h("div", { class: "eg-slivers" }); v.appendChild(box);
      var show = Math.min(Math.max(1, n), 12);             // a long file splits into hundreds: draw a dozen, count the rest
      for (var i = 0; i < show; i++) box.appendChild(h("i", { class: "eg-sliver" }));
      if (n > show) box.appendChild(h("span", { class: "eg-more", text: "+" + fmt(n - show) }));
      if (reduced()) return Promise.resolve();
      box.style.gap = "0px";
      return anim(box, [{ gap: "0px" }, { gap: "5px" }], { duration: 360, easing: css("ease-spring"), fill: "forwards" }).finished;
    }
    function visEmbedded(v) {
      var box = h("div", { class: "eg-vec" }); v.appendChild(box);
      var r = seeded(String(Date.now()));
      for (var i = 0; i < 16; i++) { var bar = h("i", { style: { height: (6 + r() * 28) + "px" } }); box.appendChild(bar);
        if (!reduced()) anim(bar, [{ transform: "scaleY(0)" }, { transform: "scaleY(1)" }], { duration: 60, delay: i * 18, easing: "steps(3, end)", fill: "backwards" }); }
      return wait(reduced() ? 0 : 16 * 18 + 60);
    }
    function visGate(v, tier, pv, kept) {
      var g = h("div", { class: "eg-gate" }, h("span", { class: "post l" }), h("span", { class: "post r" }), h("span", { class: "bar l" }), h("span", { class: "bar r" }), h("span", { class: "p", text: pv != null ? "p " + pv.toFixed(2) : "" }));
      g.style.setProperty("--c", tierColor(tier, el)); v.appendChild(g);
      if (!kept) {
        var tray = h("span", { class: "eg-tray" }), drop = h("span", { class: "eg-drop" }); v.appendChild(tray); v.appendChild(drop);
        if (reduced()) { drop.style.top = "48px"; drop.style.opacity = ".6"; return Promise.resolve(); }
        return anim(drop, [{ top: "0px", opacity: 1 }, { top: "50px", opacity: .6 }], { duration: 700, easing: "cubic-bezier(.5,0,.75,0)", fill: "forwards" }).finished;
      }
      return wait(reduced() ? 0 : tier === "S1" ? 140 : 60).then(function () { g.classList.add("open"); return wait(reduced() ? 0 : 260); });
    }
    function visExtracted(v, beliefs) {
      bins = {}; var box = h("div", { class: "eg-bins" }); v.appendChild(box);
      [["commitment", "commit"], ["decision", "decide"], ["meeting", "meet"], ["person", "people"]].forEach(function (k) {
        var n = h("b", { text: "0" }); var b = h("span", { class: "eg-bin" }, h("span", { text: k[1] }), n); bins[k[0]] = { el: b, n: n, c: 0 }; box.appendChild(b); });
      var chain = Promise.resolve();
      var people = {};
      (beliefs || []).forEach(function (bf) {
        [bf.kind].concat([bf.actor, bf.other].filter(function (x) { if (!x || people[x]) return false; people[x] = 1; return true; }).map(function () { return "person"; })).forEach(function (kind) {
          chain = chain.then(function () {
            var bin = bins[kind]; if (!bin) return;
            var land = function () { bin.c++; bin.n.textContent = String(bin.c); bin.el.classList.add("hit"); };
            if (reduced()) { land(); return; }
            var fr = h("span", { class: "eg-frag" }); v.appendChild(fr);
            var vr = v.getBoundingClientRect(), br = bin.el.getBoundingClientRect();
            var tx = br.left - vr.left + br.width / 2, ty = br.top - vr.top + br.height / 2;
            return anim(fr, [{ left: (vr.width / 2) + "px", top: "-20px", opacity: 0 }, { opacity: 1, offset: .2 }, { left: tx + "px", top: ty + "px", opacity: 1 }], { duration: 520, easing: css("ease-spring"), fill: "forwards" }).finished
              .then(function () { fr.remove(); land(); anim(bin.el, [{ transform: "scale(1.08)" }, { transform: "scale(1)" }], { duration: 240, easing: css("ease-spring") }); });
          });
        });
      });
      return chain;
    }
    function visVault(v) {
      var n = h("span", { class: "eg-note" }); var ic = Icon("note"); ic.setAttribute("class", "eg-icon"); ic.style.width = "30px"; ic.style.height = "36px"; n.appendChild(ic); v.appendChild(n);
      if (reduced()) return Promise.resolve();
      return anim(n, [{ transform: "translateY(-26px)", opacity: 0 }, { transform: "translateY(0)", opacity: 1 }], { duration: 420, easing: css("ease-spring") }).finished;
    }
    function parseGate(d) {
      var m = /^S0/.test(d), pm = /=\s*([0-9.]+)/.exec(d);
      return { tier: m ? "S0" : (/^S2/.test(d) ? "S2" : "S1"), p: pm ? parseFloat(pm[1]) : null, kept: !m };
    }
    function showStage(stage, i, state) {
      var x = st[stage.stage]; if (!x) return Promise.resolve();
      x.col.setAttribute("data-state", "active");
      x.ms.textContent = ""; x.ms.appendChild(h("span", { text: fmt(stage.ms) })); x.ms.appendChild(h("span", { class: "u", text: "ms" }));
      x.dt.textContent = stage.detail || ""; x.vis.textContent = "";
      sum += stage.ms || 0; total.textContent = fmt(sum) + " ms";
      var go;
      if (stage.stage === "stored") { var n = /(\d+) chunk/.exec(stage.detail || ""); go = visStored(x.vis, n ? +n[1] : 1); }
      else if (stage.stage === "embedded") go = visEmbedded(x.vis);
      else if (stage.stage === "gate") { var g = parseGate(stage.detail || ""); go = visGate(x.vis, g.tier, g.p, g.kept); if (!g.kept) st.extracted.col.setAttribute("data-state", "skipped"); }
      else if (stage.stage === "extracted") go = visExtracted(x.vis, state.beliefs);
      else go = visVault(x.vis);
      return go.then(function () { x.col.setAttribute("data-state", "done"); progress(STAGES.findIndex(function (s_) { return s_[0] === stage.stage; })); });
    }
    /* feed it the /api/add/<id> response each poll; it animates only what is new. */
    el.update = function (state) {
      var stages = state.stages || [];
      for (; shown < stages.length; shown++) (function (sg, i) { queue = queue.then(function () { return showStage(sg, i, state); }); })(stages[shown], shown);
      queue = queue.then(function () {
        if (state.status === "error") {
          el.classList.add("has-error"); errBox.lastChild.textContent = state.error || "failed";
          var next = STAGES.find(function (x) { return st[x[0]].col.getAttribute("data-state") === "idle"; }); if (next) st[next[0]].col.setAttribute("data-state", "error");
        }
        if (state.status === "done") {
          foot.textContent = "";
          (state.beliefs || []).forEach(function (b) { foot.appendChild(h("span", { class: "eg-belief-pill" }, h("span", { class: "k", text: b.kind }), h("span", { text: b.statement }))); });
          if (!(state.beliefs || []).length) foot.appendChild(h("span", { class: "eg-caps", text: "item " + state.item + " is searchable · nothing to remember" }));
          p.onDone && p.onDone(state);
        }
      });
      return queue;
    };
    el.reset = function (t) {
      shown = 0; sum = 0; total.textContent = ""; foot.textContent = ""; el.classList.remove("has-error"); progress(0); if (t) title.textContent = t;
      Object.keys(st).forEach(function (k) { st[k].col.setAttribute("data-state", "idle"); st[k].ms.textContent = ""; st[k].dt.textContent = ""; st[k].vis.textContent = ""; });
      queue = Promise.resolve();
    };
    return el;
  }

  /* ---------------------------------------------------------------- LedgerChain: hash-chained judgements, verified by a scan down the links */
  function LedgerChain(p) {
    p = p || {};
    var rows = [], active = { S0: true, S1: true, S2: true, H: true };
    var tbody = h("tbody");
    var verdict = h("span", { class: "eg-verdict", "aria-live": "polite" });
    var filters = h("div", { class: "eg-ledger-filters", role: "group", "aria-label": "Filter by tier" }, h("span", { class: "eg-caps", text: "tier" }));
    ["S1", "S2", "H"].forEach(function (t) {
      var c = TierChip({ tier: t, label: t + " · " + TIER_NAME[t] }); var b = h("button", { type: "button", class: c.className, "aria-pressed": "true" }); while (c.firstChild) b.appendChild(c.firstChild);
      b.addEventListener("click", function () { active[t] = !active[t]; b.setAttribute("aria-pressed", String(active[t])); apply(); p.onFilter && p.onFilter(active); });
      filters.appendChild(b);
    });
    var verifyBtn = Button({ label: "Verify chain", icon: "verify", variant: "utility", onClick: function () { p.onVerify ? p.onVerify(el) : el.verify({}); } });
    var exportBtn = Button({ label: "Export JSONL", icon: "export", variant: "pearl", onClick: function () { el.exportJSONL(); } });
    var head = h("tr", null, h("th", { "aria-label": "chain" }), ["time", "decision", "subject", "tier", "model", "value", "p", "settled", "latency", "hash"].map(function (c) {
      return h("th", { class: ["p", "latency"].indexOf(c) >= 0 ? "num" : null, scope: "col", text: c }); }));
    var el = h("div", { class: "eg eg-ledger" },
      p.bar === false ? null : h("div", { class: "eg-ledger-bar" }, filters, h("div", { style: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" } }, verdict, exportBtn, verifyBtn)),
      h("div", { class: "eg-ledger-scroll" }, h("table", null, h("thead", null, head), tbody)));
    function time(iso) {
      var d = new Date(iso); if (isNaN(d)) return iso;
      var z = function (n) { return String(n).padStart(2, "0"); };
      return z(d.getMonth() + 1) + "-" + z(d.getDate()) + " " + z(d.getHours()) + ":" + z(d.getMinutes()) + ":" + z(d.getSeconds());
    }
    function rowEl(r, fresh) {
      var tr = h("tr", { class: "eg-lrow" + (fresh ? " fresh" : ""), "data-id": r.id, "data-tier": r.tier },
        h("td", { class: "link", "aria-hidden": "true" }, h("span", { class: "eg-link" }), h("span", { class: "eg-link-node" })),
        h("td", { class: "mono muted", text: time(r.created_at) }), h("td", { text: r.question }), h("td", { class: "subj", title: r.subject, text: r.subject }),
        h("td", null, TierChip({ tier: r.tier })), h("td", { class: "mono muted", text: r.model }), h("td", { class: "mono", text: r.value }),
        h("td", { class: "num", text: r.p != null ? r.p.toFixed(2) : "—" }),
        h("td", null, h("span", { class: "eg-settled" + (r.settled ? "" : " no"), text: r.settled ? "settled" : "escalated" })),
        h("td", { class: "num", text: Math.round(r.latency_ms) + " ms" }),
        h("td", null, h("span", { class: "eg-hash", title: "links to " + (r.prev || r.prev_hash || "").slice(0, 12), text: (r.hash || "").slice(0, 12) })));
      tr._r = r; return tr;
    }
    function apply() { rows.forEach(function (tr) { tr.hidden = !active[tr._r.tier] && tr._r.tier !== "S0"; }); }
    el.verdict = verdict; el.verifyButton = verifyBtn;
    el.rows = function () { return rows.filter(function (tr) { return !tr.hidden; }).map(function (tr) { return tr._r; }); };
    el.setRows = function (rs) { tbody.textContent = ""; rows = []; (rs || []).forEach(function (r) { var tr = rowEl(r); rows.push(tr); tbody.appendChild(tr); }); apply(); };
    el.append = function (rs) { (rs || []).forEach(function (r) { var tr = rowEl(r); rows.push(tr); tbody.appendChild(tr); }); apply(); };
    el.prepend = function (r) { var tr = rowEl(r, !reduced()); rows.unshift(tr); tbody.insertBefore(tr, tbody.firstChild); apply(); };
    el.setRows(p.rows);
    /* result: the /api/ledger?verify=1 answer, e.g. {ok: true} or {first_bad: 4812, reason: "..."} */
    el.verify = function (result) {
      result = result || {};
      rows.forEach(function (tr) { tr.classList.remove("ok", "bad", "scan", "after"); var nx = tr.nextSibling; if (nx && nx.classList.contains("explain")) nx.remove(); });
      verdict.className = "eg-verdict"; verdict.textContent = "verifying…"; verifyBtn.disabled = true;
      var vis = rows.filter(function (tr) { return !tr.hidden; }).slice().sort(function (a, b) { return a._r.id - b._r.id; }); /* oldest first: the chain runs from genesis up */
      var step = reduced() ? 0 : Math.max(12, Math.min(160, 2400 / Math.max(1, vis.length)));   /* a scan takes ≤ 2.4 s */
      var chain = Promise.resolve(), stopped = false;
      vis.forEach(function (tr) {
        chain = chain.then(function () {
          if (stopped) { tr.classList.add("after"); return; }
          tr.classList.add("scan");
          return wait(step).then(function () {
            tr.classList.remove("scan");
            if (result.first_bad != null && Number(tr._r.id) >= Number(result.first_bad)) {
              stopped = true; tr.classList.add("bad");
              var ex = h("tr", { class: "explain" }, h("td"), h("td", { colspan: "10" }, h("strong", { text: "Chain breaks at judgement " + result.first_bad + (Number(tr._r.id) === Number(result.first_bad) ? ". " : ", just before this row (hidden by your filters). ") }), result.reason || "Its stored hash is not sha256(prev_hash ‖ row): this row, or one before it, was altered after it was written. Every row above it is unverified."));
              tr.after(ex);
            } else tr.classList.add("ok");
          });
        });
      });
      return chain.then(function () {
        verifyBtn.disabled = false;
        if (stopped) { verdict.className = "eg-verdict bad"; verdict.textContent = "Chain broken at #" + result.first_bad; verdict.insertBefore(Icon("alert", { size: "sm" }), verdict.firstChild); }
        else { verdict.textContent = vis.length + " links verified"; verdict.insertBefore(Icon("check", { size: "sm" }), verdict.firstChild); }
      });
    };
    el.exportJSONL = function () {
      var txt = rows.filter(function (tr) { return !tr.hidden; }).map(function (tr) { return JSON.stringify(tr._r); }).join("\n") + "\n";
      var a = h("a", { href: URL.createObjectURL(new Blob([txt], { type: "application/x-ndjson" })), download: "engram-ledger.jsonl" });
      document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
      return txt;
    };
    return el;
  }

  /* ---------------------------------------------------------------- ApprovalCard: what the gate escalated to you */
  function ApprovalCard(p) {
    p = p || {};
    var doneTxt = h("span"), mark = h("span", { class: "mark" });
    var el = h("section", { class: "eg eg-approval eg-tile eg-ontile", "aria-label": "Approval waiting on you" },
      h("div", { class: "row" }, TierChip({ tier: "H", label: "Waiting on you", live: true, onTile: true }), p.risk ? h("span", { class: "eg-caps", text: "risk · " + p.risk }) : null),
      h("p", { class: "req", text: p.request || "" }),
      p.preview ? h("pre", { text: p.preview }) : null,
      p.why ? h("div", { class: "why" }, TierChip({ tier: "S2", onTile: true }), " ", p.why) : null,
      h("div", { class: "acts" },
        Button({ label: "Approve", icon: "check", onClick: function () { el.resolve(true, "page"); p.onApprove && p.onApprove(); } }),
        Button({ label: "Deny", variant: "secondary", className: "on-tile", onClick: function () { el.resolve(false, "page"); p.onDeny && p.onDeny(); } })),
      h("div", { class: "done", role: "status" }, mark, doneTxt),
      p.channels ? h("div", { class: "row", style: { color: "var(--on-tile-muted)", fontSize: "12px" } }, Icon("watch", { size: "sm" }), "also on " + p.channels) : null);
    var t0 = performance.now();
    el.resolve = function (ok, channel) {
      var sec = ((performance.now() - t0) / 1000).toFixed(1);
      el.classList.add("resolved"); el.classList.toggle("denied", !ok);
      mark.textContent = ""; mark.appendChild(Icon(ok ? "check" : "x", { size: "sm" }));
      doneTxt.textContent = (ok ? "Approved" : "Denied") + (channel === "watch" ? " on the watch" : "") + " · " + sec + " s · recorded as H in the ledger";
      var chip = el.querySelector(".eg-chip--H"); chip && chip.setAttribute("data-live", "false");
      if (!reduced()) anim(mark, [{ transform: "scale(.4)", opacity: 0 }, { transform: "scale(1)", opacity: 1 }], { duration: 300, easing: css("ease-spring") });
    };
    return el;
  }

  /* ---------------------------------------------------------------- CommandPalette (⌘K) */
  function CommandPalette(p) {
    p = p || {};
    var items = p.items || [], sel = 0, shown = [];
    var input = h("input", { type: "text", placeholder: p.placeholder || "Search items, beliefs, people, agents, views", "aria-label": "Command", role: "combobox", "aria-expanded": "true", "aria-controls": "eg-cmdk-list", autocomplete: "off" });
    var list = h("ul", { class: "eg-cmdk-list", id: "eg-cmdk-list", role: "listbox" });
    var sheet = h("div", { class: "eg eg-cmdk", role: "dialog", "aria-label": "Command palette", "aria-modal": p.inline ? null : "true" },
      h("div", { class: "eg-cmdk-in" }, Icon("search"), input, h("span", { class: "eg-kbd", text: "esc" })), list,
      h("div", { class: "eg-cmdk-foot" }, h("span", null, h("span", { class: "eg-kbd", text: "↑↓" }), " move"), h("span", null, h("span", { class: "eg-kbd", text: "↵" }), " open"), h("span", { class: "eg-num", style: { marginLeft: "auto" } })));
    var root = p.inline ? sheet : h("div", { class: "eg-cmdk-scrim", onClick: function (e) { if (e.target === root) close(); } }, sheet);
    function mark(text, q) { var i = text.toLowerCase().indexOf(q.toLowerCase()); if (!q || i < 0) return [text]; return [text.slice(0, i), h("mark", { text: text.slice(i, i + q.length) }), text.slice(i + q.length)]; }
    function render() {
      var q = input.value.trim(); list.textContent = "";
      shown = items.filter(function (it) { return !q || it.always || (it.title + " " + (it.meta || "") + " " + (it.keywords || "")).toLowerCase().indexOf(q.toLowerCase()) >= 0; });
      sel = Math.min(sel, Math.max(0, shown.length - 1));
      var group = null;
      shown.forEach(function (it, i) {
        if (it.group !== group) { group = it.group; list.appendChild(h("li", { class: "eg-cmdk-group eg-caps", role: "presentation", text: group })); }
        var li = h("li", { class: "eg-cmdk-item", role: "option", id: "eg-cmdk-" + i, "aria-selected": String(i === sel), onClick: function () { choose(i); }, onMousemove: function () { if (sel !== i) { sel = i; mark_(); } } },
          it.tier ? h("span", { class: "eg-dot", style: { color: "inherit" } }) : Icon(it.icon || "chevron", { size: "sm" }), h("span", null, mark(it.title, q)),
          it.tier ? TierChip({ tier: it.tier }) : h("span", { class: "meta", text: it.meta || "" }));
        list.appendChild(li);
      });
      if (!shown.length) list.appendChild(h("li", { class: "eg-cmdk-empty", text: "Nothing in this brain matches “" + q + "”." }));
      sheet.querySelector(".eg-cmdk-foot .eg-num").textContent = shown.length + " of " + items.length;
      mark_();
    }
    function mark_() { list.querySelectorAll(".eg-cmdk-item").forEach(function (li, i) { li.setAttribute("aria-selected", String(i === sel)); if (i === sel) { input.setAttribute("aria-activedescendant", li.id); li.scrollIntoView({ block: "nearest" }); } }); }
    function choose(i) { var it = shown[i]; if (it && p.onChoose) p.onChoose(it); if (!p.inline) close(); }
    input.addEventListener("input", function () { sel = 0; render(); if (p.onQuery) p.onQuery(input.value.trim()); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); sel = Math.min(shown.length - 1, sel + 1); mark_(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sel = Math.max(0, sel - 1); mark_(); }
      else if (e.key === "Enter") { e.preventDefault(); choose(sel); }
      else if (e.key === "Escape") { e.preventDefault(); close(); }
    });
    var opener = null;
    function open() { opener = document.activeElement; if (!p.inline) document.body.appendChild(root); input.value = ""; sel = 0; render(); input.focus();
      if (!reduced()) anim(sheet, [{ opacity: 0, transform: "translateY(-8px) scale(.98)" }, { opacity: 1, transform: "none" }], { duration: ms("dur-ui", 240), easing: css("ease-spring") }); }
    function close() { if (p.inline) { input.value = ""; render(); return; } var a = reduced() ? { finished: Promise.resolve() } : anim(sheet, [{ opacity: 1 }, { opacity: 0, transform: "translateY(-4px)" }], { duration: 150 }); a.finished.then(function () { root.remove(); opener && opener.focus && opener.focus(); }); }
    render();
    root.open = open; root.close = close;
    root.setItems = function (next) { items = next || []; render(); };
    root.type = function (text, every) { input.focus(); var i = 0; every = reduced() ? 0 : (every || 70); return new Promise(function (res) { (function tick() { if (i > text.length) return res(); input.value = text.slice(0, i++); sel = 0; render(); setTimeout(tick, every); })(); }); };
    root.bindShortcut = function () { document.addEventListener("keydown", function (e) { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); } }); };
    return root;
  }

  /* ---------------------------------------------------------------- BeliefTimeline: bitemporal (valid time × recorded time) */
  function BeliefTimeline(p) {
    p = p || {};
    var bs = (p.beliefs || []).map(function (b) { return Object.assign({}, b, { vs: +new Date(b.valid[0]), ve: b.valid[1] ? +new Date(b.valid[1]) : null, rs: +new Date(b.recorded[0]), re: b.recorded[1] ? +new Date(b.recorded[1]) : null }); });
    var W = p.width || 860, H = p.height || 330, L = 56, R = 16, T = 30, B = 34;
    var vmin = Math.min.apply(null, bs.map(function (b) { return b.vs; })), vmax = Math.max.apply(null, bs.map(function (b) { return b.ve || b.vs; }));
    var rmin = Math.min.apply(null, bs.map(function (b) { return b.rs; })), rmax = Math.max.apply(null, bs.map(function (b) { return b.re || b.rs; }));
    var vpad = (vmax - vmin) * 0.08 || 864e5, rpad = (rmax - rmin) * 0.1 || 864e5; vmin -= vpad; vmax += vpad * 2; rmin -= rpad; rmax += rpad * 2;
    var X = function (t) { return L + (t - vmin) / (vmax - vmin) * (W - L - R); };
    var Y = function (t) { return T + (t - rmin) / (rmax - rmin) * (H - T - B); };
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "Beliefs on a bitemporal timeline: across is when a belief holds in the world, down is when the brain held it" });
    svg.appendChild(s("line", { class: "axis", x1: L, x2: W - R, y1: H - B, y2: H - B })); svg.appendChild(s("line", { class: "axis", x1: L, x2: L, y1: T, y2: H - B }));
    var local = function (t) { var d = new Date(t); return new Date(t - d.getTimezoneOffset() * 6e4).toISOString(); };   // this machine's clock
    var fmtFor = function (span) { return function (t) { var iso = local(t); return span > 400 * 864e5 ? iso.slice(0, 7) : span > 20 * 864e5 ? iso.slice(0, 10) : span > 2 * 864e5 ? iso.slice(5, 10) + " " + iso.slice(11, 13) + "h" : iso.slice(11, 16); }; };
    var years = function (a, b) { var y1 = local(a).slice(0, 4), y2 = local(b).slice(0, 4); return y1 === y2 ? y1 : y1 + "–" + y2; };
    var dv = fmtFor(vmax - vmin), dr = fmtFor(rmax - rmin), placed = [];
    for (var i = 0; i <= 4; i++) {
      var tv = vmin + (vmax - vmin) * i / 4, tr = rmin + (rmax - rmin) * i / 4;
      var a = s("text", { class: "tick", x: X(tv), y: H - B + 14, "text-anchor": "middle" }); a.textContent = dv(tv); svg.appendChild(a);
      var b = s("text", { class: "tick", x: L - 6, y: Y(tr) + 3, "text-anchor": "end" }); b.textContent = dr(tr); svg.appendChild(b);
    }
    var ax = s("text", { class: "axl", x: W - R, y: H - 4, "text-anchor": "end" }); ax.textContent = "VALID TIME" + (vmax - vmin > 20 * 864e5 ? "" : " · " + years(vmin, vmax)) + " →"; svg.appendChild(ax);
    var ay = s("text", { class: "axl", x: 4, y: 10 }); ay.textContent = "RECORDED" + (rmax - rmin > 20 * 864e5 ? "" : " · " + local(rmin).slice(0, 10)) + " ↓"; svg.appendChild(ay);
    var groups = [], byId = {};
    bs.forEach(function (b) { byId[b.id] = b; });
    var strands = s("g"); svg.appendChild(strands);
    var area = function (b) { return ((b.ve || vmax) - b.vs) * ((b.re || rmax) - b.rs); };
    bs.slice().sort(function (a, b) { return area(b) - area(a); }).forEach(function (b) {
      var x1 = X(b.vs), x2 = b.ve ? X(b.ve) : W - R, y1 = Y(b.rs), y2 = b.re ? Y(b.re) : H - B;
      var cur = !b.re, g = s("g", { class: "b", tabindex: "0", role: "button", "aria-label": b.kind + ": " + b.statement + (cur ? " (current)" : " (superseded)") });
      // a superseded belief is a closed box; a current one would run to both edges, and dozens of those stacked
      // hide everything, so it is a ray along the moment it was recorded, fading while it still holds
      if (cur) {
        g.appendChild(s("rect", { class: "hit", x: x1, y: y1 - 6, width: Math.max(8, x2 - x1), height: 12 }));
        g.appendChild(s("path", { class: "ray" + (b.ve ? " closed" : ""), d: "M" + x1 + " " + y1 + " H " + Math.max(x1 + 4, x2) }));
      } else g.appendChild(s("rect", { class: "band old", x: x1, y: y1, width: Math.max(4, x2 - x1), height: Math.max(3, y2 - y1), rx: 3 }));
      var mx = x1, my = y1, r = 5, mk;
      if (b.kind === "commitment") mk = s("circle", { cx: mx, cy: my, r: r });
      else if (b.kind === "decision") mk = s("path", { d: "M" + mx + " " + (my - r - 1) + "L" + (mx + r + 1) + " " + my + "L" + mx + " " + (my + r + 1) + "L" + (mx - r - 1) + " " + my + "Z" });
      else mk = s("rect", { x: mx - r, y: my - r, width: r * 2, height: r * 2 });
      mk.setAttribute("class", "mk " + (b.tier || "S2")); g.appendChild(mk);
      var txt = (b.short || b.statement).slice(0, Math.max(12, Math.min(56, Math.floor((W - R - x1) / 6.5)))), lx = x1 + 10, ly = y1 + 14, lw = txt.length * 6;
      var free = !placed.some(function (q) { return Math.abs(q.y - ly) < 14 && lx < q.x + q.w && q.x < lx + lw; });
      if ((cur || bs.length <= 12) && free) { var lb = s("text", { class: "lbl" + (cur ? "" : " old"), x: lx, y: ly }); lb.textContent = txt; g.appendChild(lb); placed.push({ x: lx, y: ly, w: lw }); }
      g._b = b; groups.push(g); svg.appendChild(g);
      if (b.supersedes && byId[b.supersedes]) {
        var o = byId[b.supersedes], sx = X(o.vs) + 6, sy = Y(o.re || o.rs);
        var path = s("path", { class: "strand", d: "M" + sx + " " + sy + " C " + sx + " " + (sy + 30) + ", " + x1 + " " + (y1 - 30) + ", " + x1 + " " + y1 });
        path._pair = [o.id, b.id]; strands.appendChild(path);
      }
    });
    var detail = h("div", { class: "eg-tl-detail", "aria-live": "polite" }, h("span", { class: "eg-caps", text: "select a belief for its provenance" }));
    function show(b) {
      detail.textContent = "";
      detail.appendChild(h("div", null, h("span", { class: "eg-caps", text: b.kind + " · " + (b.re ? "superseded" : "current") + " · " }), TierChip({ tier: b.tier || "S2", onTile: true }), " ", h("span", { class: "m", text: "p " + (b.confidence != null ? b.confidence.toFixed(2) : "—") + " · item:" + b.item_id })));
      detail.appendChild(h("div", { style: { marginTop: "6px" }, text: b.statement }));
      if (b.quote) detail.appendChild(h("div", { style: { marginTop: "4px" } }, h("q", { text: b.quote })));
    }
    groups.forEach(function (g) { g.addEventListener("click", function () { show(g._b); p.onSelect && p.onSelect(g._b); }); g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(g._b); } }); });
    var fk = { kind: null, person: null };
    function apply() {
      groups.forEach(function (g) { var b = g._b; var on = (!fk.kind || b.kind === fk.kind) && (!fk.person || b.actor === fk.person || b.other === fk.person); g.classList.toggle("dim", !on); });
      strands.querySelectorAll("path").forEach(function (pth) { pth.style.opacity = groups.some(function (g) { return g._b.id === pth._pair[1] && !g.classList.contains("dim"); }) ? "" : ".1"; });
    }
    var fbar = h("div", { class: "eg-tl-filters", role: "group", "aria-label": "Filter beliefs" });
    function fbtn(label, key, val) {
      var b = h("button", { type: "button", "aria-pressed": "false", text: label, onClick: function () { fk[key] = fk[key] === val ? null : val; fbar.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", String(fk[x._k] === x._v && x._v != null)); }); apply(); } });
      b._k = key; b._v = val; fbar.appendChild(b);
    }
    ["commitment", "decision", "meeting"].forEach(function (k) { fbtn(k + "s", "kind", k); });
    (p.people || []).forEach(function (n) { fbtn(n, "person", n); });
    var el = h("div", { class: "eg eg-tl eg-tile eg-ontile" }, fbar, svg, detail);
    if (!reduced()) requestAnimationFrame(function () {
      strands.querySelectorAll("path").forEach(function (pth, i) { var len = pth.getTotalLength(); pth.style.strokeDasharray = len; anim(pth, [{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 900, delay: 300 + i * 120, easing: css("ease-s2"), fill: "backwards" }); });
      groups.forEach(function (g, i) { anim(g, [{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }], { duration: 320, delay: i * 50, easing: css("ease-standard"), fill: "backwards" }); });
    });
    return el;
  }

  /* ---------------------------------------------------------------- SchemaAtlas: tables sized by rows, FK edges, columns on select */
  function SchemaAtlas(p) {
    p = p || {};
    var tables = p.tables || [], W = p.width || 620, H = p.height || 380;
    var max = Math.max.apply(null, tables.map(function (t) { return t.rows || 1; }).concat([1]));
    var R = function (t) { return 14 + 26 * Math.log10(1 + (t.rows || 0)) / Math.log10(1 + max); };
    var svg = s("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "Database schema" });
    var byName = {}; tables.forEach(function (t, i) { t._x = (t.x != null ? t.x : 0.5 + 0.38 * Math.cos(i / tables.length * 6.283)) * W; t._y = (t.y != null ? t.y : 0.5 + 0.38 * Math.sin(i / tables.length * 6.283)) * H; byName[t.name] = t; });
    // the layout places centres only: push apart any two footprints (the circle and the name under it) that overlap
    var half = function (t) { return [Math.max(R(t), t.name.length * 3.4) + 6, R(t) + 12]; };
    for (var it = 0; it < 200; it++) {
      var moved = false;
      for (var i = 0; i < tables.length; i++) for (var j = i + 1; j < tables.length; j++) {
        var a = tables[i], b = tables[j], ha = half(a), hb = half(b), dx = b._x - a._x, dy = b._y - a._y;
        var ox = ha[0] + hb[0] - Math.abs(dx), oy = ha[1] + hb[1] - Math.abs(dy);
        if (ox <= 0 || oy <= 0) continue;
        moved = true;
        if (ox < oy) { var sx = (dx < 0 ? -1 : 1) * ox / 2; a._x -= sx; b._x += sx; } else { var sy = (dy < 0 ? -1 : 1) * oy / 2; a._y -= sy; b._y += sy; }
      }
      tables.forEach(function (t) { var hw = half(t)[0]; t._x = Math.min(W - hw, Math.max(hw, t._x)); t._y = Math.min(H - R(t) - 20, Math.max(R(t) + 4, t._y)); });
      if (!moved) break;
    }
    var edges = [];
    (p.fks || []).forEach(function (f) {
      var a = byName[f[0]], b = byName[f[1]]; if (!a || !b) return;
      var d = a === b ? "M" + (a._x + R(a) * .7) + " " + (a._y - R(a) * .7) + " a 16 16 0 1 1 " + (R(a) * .3) + " " + (R(a) * .9)
        : "M" + a._x + " " + a._y + " Q " + ((a._x + b._x) / 2 + (b._y - a._y) * .12) + " " + ((a._y + b._y) / 2 - (b._x - a._x) * .12) + " " + b._x + " " + b._y;
      var e = s("path", { class: "fk", d: d }); e._ab = [f[0], f[1]]; edges.push(e); svg.appendChild(e);
    });
    var side = h("div", { class: "eg-atlas-side", "aria-live": "polite" }, h("span", { class: "eg-caps", text: "select a table" }));
    var gs = [];
    tables.forEach(function (t) {
      var g = s("g", { class: "t" + (t.view ? " view" : ""), tabindex: "0", role: "button", "aria-label": t.name + (t.view ? " (view)" : "") + ", " + fmt(t.rows) + " rows" });
      g.appendChild(s("circle", { cx: t._x, cy: t._y, r: R(t) }));
      var n = s("text", { class: "nm", x: t._x, y: t._y + R(t) + 15 }); n.textContent = t.name; g.appendChild(n);
      var c = s("text", { class: "ct", x: t._x, y: t._y + 4 }); c.textContent = t.rows != null ? fmt(t.rows) : "view"; g.appendChild(c);
      g._t = t; gs.push(g); svg.appendChild(g);
      var pick = function () {
        gs.forEach(function (x) { x.classList.toggle("sel", x === g); });
        edges.forEach(function (e) { e.classList.toggle("on", e._ab.indexOf(t.name) >= 0); });
        side.textContent = "";
        side.appendChild(h("h4", { text: t.name })); side.appendChild(h("span", { class: "eg-caps", text: (t.view ? "view" : fmt(t.rows) + " rows") }));
        side.appendChild(h("ul", null, (t.columns || []).map(function (col) { return h("li", null, h("span", { text: col[0] }), h("span", { text: col[1] })); })));
        p.onSelect && p.onSelect(t);
      };
      g.addEventListener("click", pick); g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
    });
    var el = h("div", { class: "eg eg-atlas eg-tile eg-ontile" }, svg, side);
    el.side = side;
    if (!reduced()) requestAnimationFrame(function () {
      gs.forEach(function (g, i) { var c = g.querySelector("circle"); anim(c, [{ r: 0 }, { r: c.getAttribute("r") }], { duration: 420, delay: i * 40, easing: css("ease-spring"), fill: "backwards" }); });
      edges.forEach(function (e, i) { var len = e.getTotalLength(); e.style.strokeDasharray = len; anim(e, [{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 500, delay: 300 + i * 60, easing: css("ease-standard"), fill: "backwards" }); });
    });
    el.setCount = function (name, n) { var g = gs.find(function (x) { return x._t.name === name; }); if (!g) return; g._t.rows = n; g.querySelector(".ct").textContent = fmt(n); if (!reduced()) anim(g.querySelector(".ct"), [{ opacity: .2 }, { opacity: 1 }], { duration: 240 }); };
    return el;
  }


export { Icon, Button, TierChip, Readout, TopBar, Segmented, ProfileTile, Constellation, Switchboard, AgentDrawer,
  Sparkline, Pipeline, LedgerChain, ApprovalCard, CommandPalette, BeliefTimeline, SchemaAtlas, reduced as reducedMotion,
  TIERS, TIER_NAME, h, s as svg, css, tierColor, anim, wait, settle, fmt, seeded, transition };
