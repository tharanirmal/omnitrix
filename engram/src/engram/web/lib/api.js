// The page's only way to the server: same-origin JSON. A 401 anywhere means the session ended (idle timeout, restart,
// sign-out in another tab): the app hears it as `engram:signed-out` and shows the brains again.

export class ApiError extends Error {
  constructor(status, body) {
    super((body && body.error) || `HTTP ${status}`);
    this.status = status;
    this.body = body || {};
  }
}

export async function api(path, body, opts = {}) {
  const init = body === undefined
    ? { credentials: "same-origin", signal: opts.signal }
    : { method: "POST", credentials: "same-origin", signal: opts.signal, headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) };
  const r = await fetch(path, init);
  let data = null;
  try { data = await r.json(); } catch { /* not JSON */ }
  if (r.status === 401 && !path.startsWith("/api/login")) window.dispatchEvent(new CustomEvent("engram:signed-out"));
  if (!r.ok) throw new ApiError(r.status, data);
  return data;
}

/* A tiny event bus over window: the pollers publish, the views subscribe while mounted. */
export function emit(name, detail) { window.dispatchEvent(new CustomEvent(`engram:${name}`, { detail })); }
export function on(name, fn) {
  const h = (e) => fn(e.detail);
  window.addEventListener(`engram:${name}`, h);
  return () => window.removeEventListener(`engram:${name}`, h);
}

/* Repeat `fn` every `ms` until stopped; a failing call waits longer (up to 30 s) instead of hammering. */
export function every(ms, fn) {
  let stopped = false, timer = 0, delay = ms;
  const tick = async () => {
    if (stopped) return;
    try { await fn(); delay = ms; } catch (e) { if (e.status === 401) return; delay = Math.min(delay * 2, 30000); }
    if (!stopped) timer = setTimeout(tick, document.hidden ? Math.max(delay, 5000) : delay);
  };
  tick();
  return () => { stopped = true; clearTimeout(timer); };
}

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
