import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { getApiBase, getWsUrl, setApiBase } from "@/config";
import { api } from "@/lib/api";
import { announce, dropFromQueue, setVoiceEnabled, voiceSupported } from "@/lib/voice";
import type { RestartPlan, Snapshot } from "@/types";
import mockStart from "@/mocks/snapshot_start.json";
import mockEmergency from "@/mocks/snapshot_emergency.json";

export type ConnState = "connecting" | "live" | "reconnecting" | "demo";
type DemoScenario = "start" | "emergency";

interface LiveCtx {
  snap: Snapshot | null;
  conn: ConnState;
  demo: boolean;
  demoScenario: DemoScenario;
  setDemoScenario: (s: DemoScenario) => void;
  apiBase: string;
  changeApiBase: (url: string | null) => void;
  /** Run a POST action; refetches snapshot afterwards. Returns result or null on failure. */
  act: <T>(fn: () => Promise<T>) => Promise<T | null>;
  applied: { title: string; items: string[] } | null;
  showApplied: (title: string, items: string[]) => void;
  clearApplied: () => void;
  restartPlan: RestartPlan | null;
  setRestartPlan: (p: RestartPlan | null) => void;
  voiceOn: boolean;
  setVoiceOn: (v: boolean) => void;
  voiceAsked: boolean;
  testVoice: () => void;
}

// Keep one context instance across hot reloads so providers and consumers always match.
const g = globalThis as unknown as { __shiftloopLiveCtx?: React.Context<LiveCtx | null> };
const Ctx = g.__shiftloopLiveCtx ?? (g.__shiftloopLiveCtx = createContext<LiveCtx | null>(null));
export const useLive = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useLive outside provider");
  return c;
};

const VOICE_KEY = "shiftloop_voice";

export function LiveProvider({ children }: { children: ReactNode }) {
  const [liveSnap, setLiveSnap] = useState<Snapshot | null>(null);
  const [conn, setConn] = useState<ConnState>("connecting");
  const [demo, setDemo] = useState(false);
  const [demoScenario, setDemoScenario] = useState<DemoScenario>("start");
  const [apiBase, setApiBaseState] = useState("");
  const [gen, setGen] = useState(0);
  const [applied, setApplied] = useState<{ title: string; items: string[] } | null>(null);
  const [restartPlan, setRestartPlan] = useState<RestartPlan | null>(null);
  const [voiceOn, setVoiceOnState] = useState(false);
  const [voiceAsked, setVoiceAsked] = useState(true);

  // voice prefs
  useEffect(() => {
    const v = localStorage.getItem(VOICE_KEY);
    setVoiceAsked(v !== null);
    const on = v === "on";
    setVoiceOnState(on);
    setVoiceEnabled(on);
  }, []);
  const setVoiceOn = useCallback((v: boolean) => {
    localStorage.setItem(VOICE_KEY, v ? "on" : "off");
    setVoiceAsked(true);
    setVoiceOnState(v);
    setVoiceEnabled(v);
    if (v && voiceSupported()) {
      const u = new SpeechSynthesisUtterance("Voice alerts active.");
      u.rate = 1.05; u.lang = "en-US";
      window.speechSynthesis.speak(u);
    }
  }, []);
  const testVoice = useCallback(() => {
    if (!voiceSupported()) { toast.error("Voice not supported in this browser"); return; }
    const u = new SpeechSynthesisUtterance("Voice alerts active.");
    u.rate = 1.05; u.lang = "en-US";
    window.speechSynthesis.speak(u);
  }, []);

  // connection
  useEffect(() => {
    setApiBaseState(getApiBase());
    let ws: WebSocket | null = null;
    let closed = false;
    let reconnectT: ReturnType<typeof setTimeout> | null = null;
    let pollT: ReturnType<typeof setInterval> | null = null;
    let gotData = false;
    setConn("connecting");

    const onSnap = (s: Snapshot) => {
      gotData = true;
      setLiveSnap(s);
      setDemo(false);
    };
    const startPoll = () => {
      if (pollT) return;
      pollT = setInterval(() => {
        api.snapshot().then(onSnap).catch(() => {});
      }, 3000);
    };
    const stopPoll = () => { if (pollT) { clearInterval(pollT); pollT = null; } };

    const open = () => {
      if (closed) return;
      try { ws = new WebSocket(getWsUrl()); } catch { scheduleReconnect(); return; }
      ws.onopen = () => { setConn("live"); stopPoll(); };
      ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data);
          if (m && m.type === "snapshot" && m.data) { onSnap(m.data as Snapshot); setConn("live"); }
        } catch { /* ignore */ }
      };
      ws.onclose = () => { if (!closed) scheduleReconnect(); };
      ws.onerror = () => { try { ws?.close(); } catch { /* */ } };
    };
    const scheduleReconnect = () => {
      setConn((c) => (c === "demo" ? c : "reconnecting"));
      startPoll();
      if (reconnectT) clearTimeout(reconnectT);
      reconnectT = setTimeout(open, 1500);
    };
    open();
    api.snapshot().then(onSnap).catch(() => {});
    const demoT = setTimeout(() => { if (!gotData) { setDemo(true); setConn("demo"); } }, 5000);

    return () => {
      closed = true;
      clearTimeout(demoT);
      if (reconnectT) clearTimeout(reconnectT);
      stopPoll();
      try { ws?.close(); } catch { /* */ }
    };
  }, [gen]);

  // once live data arrives after demo, conn reflects it
  useEffect(() => { if (!demo && liveSnap && conn === "demo") setConn("reconnecting"); }, [demo, liveSnap, conn]);

  const snap: Snapshot | null = demo
    ? ((demoScenario === "start" ? mockStart : mockEmergency) as unknown as Snapshot)
    : liveSnap;

  // voice announcements
  const seen = useRef<Set<string> | null>(null);
  const lastSpoken = useRef<Map<string, number>>(new Map());
  const snapRef = useRef<Snapshot | null>(null);
  snapRef.current = snap;
  useEffect(() => {
    if (!snap) return;
    const ns = snap.notifications ?? [];
    if (seen.current === null) {
      seen.current = new Set(ns.map((n) => n.id));
      return;
    }
    for (const n of ns) {
      if (n.acknowledged) { dropFromQueue(n.id); lastSpoken.current.delete(n.id); continue; }
      if (seen.current.has(n.id)) continue;
      seen.current.add(n.id);
      if (!n.spoken || n.level === "info") continue;
      announce(n.id, n.spoken, n.level === "critical");
      if (n.level === "critical") lastSpoken.current.set(n.id, Date.now());
    }
  }, [snap]);
  useEffect(() => {
    const t = setInterval(() => {
      const s = snapRef.current;
      if (!s) return;
      for (const [id, at] of lastSpoken.current) {
        const n = s.notifications.find((x) => x.id === id);
        if (!n || n.acknowledged) { lastSpoken.current.delete(id); dropFromQueue(id); continue; }
        if (Date.now() - at >= 60000 && n.spoken) {
          announce(id, n.spoken, true);
          lastSpoken.current.set(id, Date.now());
        }
      }
    }, 5000);
    return () => clearInterval(t);
  }, []);

  const act = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | null> => {
    if (demo) { toast("Connect a backend to act"); return null; }
    try {
      const r = await fn();
      api.snapshot().then((s) => setLiveSnap(s)).catch(() => {});
      return r;
    } catch {
      return null;
    }
  }, [demo]);

  const changeApiBase = useCallback((url: string | null) => {
    setApiBase(url);
    setLiveSnap(null);
    seen.current = null;
    setGen((g) => g + 1);
  }, []);

  return (
    <Ctx.Provider
      value={{
        snap, conn, demo, demoScenario, setDemoScenario, apiBase, changeApiBase, act,
        applied, showApplied: (title, items) => setApplied({ title, items }), clearApplied: () => setApplied(null),
        restartPlan, setRestartPlan, voiceOn, setVoiceOn, voiceAsked, testVoice,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}
