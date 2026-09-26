const KEY = "shiftloop_api";

/** Resolve API base: ?api= → localStorage → VITE_API_BASE_URL → "" (same origin). Browser only. */
export function resolveApiBase(): string {
  if (typeof window === "undefined") return "";
  try {
    const q = new URLSearchParams(window.location.search).get("api");
    if (q) {
      const v = q.replace(/\/+$/, "");
      localStorage.setItem(KEY, v);
      return v;
    }
    const s = localStorage.getItem(KEY);
    if (s) return s;
  } catch {
    /* ignore */
  }
  const env = (import.meta.env['VITE_API_BASE_URL'] as string | undefined) ?? "";
  return env.replace(/\/+$/, "");
}

let base: string | null = null;
export function getApiBase(): string {
  if (base === null) base = resolveApiBase();
  return base;
}
export function setApiBase(url: string | null) {
  const v = (url ?? "").trim().replace(/\/+$/, "");
  try {
    if (v) localStorage.setItem(KEY, v);
    else localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  base = v || ((import.meta.env['VITE_API_BASE_URL'] as string | undefined) ?? "").replace(/\/+$/, "");
}

export function getWsUrl(): string {
  const b = getApiBase();
  if (!b) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/ws`;
  }
  return b.replace(/^http/, "ws") + "/ws";
}
