const KEY = "shiftloop_api";
/** Hosted backend used when nothing else is configured. */
export const DEFAULT_API = "https://shiftloop.onrender.com";

/**
 * DEMO MODE SWITCH — set to false (or delete src/mocks/) once the real
 * backend is hosted. When true, the app opens instantly on the mock
 * snapshots in src/mocks/ and shows the DEMO DATA badge; a reachable
 * backend still takes over automatically. When false, no dummy data is
 * ever shown and the app waits for the backend.
 */
export const DEMO_ENABLED = true;

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
  const env = (import.meta.env['VITE_API_BASE_URL'] as string | undefined) || DEFAULT_API;
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
  base = v || ((import.meta.env['VITE_API_BASE_URL'] as string | undefined) || DEFAULT_API).replace(/\/+$/, "");
}

export function getWsUrl(): string {
  const b = getApiBase();
  if (!b) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/ws`;
  }
  return b.replace(/^http/, "ws") + "/ws";
}
