import { toast } from "sonner";
import { getApiBase } from "@/config";
import type {
  ChatResponse, Decision, Escalation, HandoverResponse, Language, ModifiedAssignment,
  Notification, Oversight, Proposal, RestartPlan, SimCommand, SimStatus, Snapshot, WhatIfResult, Worker,
} from "@/types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(method: "GET" | "POST", path: string, body?: unknown, timeoutMs = 15000, silent = false): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const init: RequestInit = { method, signal: ctrl.signal };
    if (method === "POST") {
      init.headers = { "content-type": "application/json" };
      init.body = JSON.stringify(body ?? {});
    }
    const res = await fetch(getApiBase() + path, init);
    if (!res.ok) {
      let detail = `Request failed (${res.status})`;
      try { const j = await res.json(); if (j && typeof j.detail === "string") detail = j.detail; } catch { /* */ }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  } catch (e) {
    const msg = e instanceof ApiError ? e.message : (e as Error).name === "AbortError" ? "Request timed out" : "Backend not reachable";
    if (!silent) toast.error(msg);
    throw e instanceof ApiError ? e : new ApiError(0, msg);
  } finally {
    clearTimeout(t);
  }
}

export type Health = { ok: boolean; mode: "claude" | "offline"; vision: Record<string, string> };
type Stations = { id: string; zone: string; name: string; safety_critical: boolean }[];

export const api = {
  health: () => req<Health>("GET", "/api/health", undefined, 5000, true),
  snapshot: (silent = true) => req<Snapshot>("GET", "/api/snapshot", undefined, 5000, silent),
  workers: () => req<{ workers: Worker[]; stations: Stations }>("GET", "/api/workers"),
  oversight: () => req<Oversight>("GET", "/api/oversight"),
  sim: (cmd: SimCommand) => req<SimStatus>("POST", "/api/sim", cmd),
  decide: (id: string, body: { decision: "accept" | "modify" | "dismiss"; reason: string; assignments?: ModifiedAssignment[] }) =>
    req<Decision>("POST", `/api/incidents/${id}/decision`, body),
  ackNotification: (id: string) => req<Notification>("POST", `/api/notifications/${id}/ack`, {}),
  ackEscalation: (id: string) => req<Escalation>("POST", `/api/escalations/${id}/ack`, {}),
  whatif: (worker: string, station: string) => req<WhatIfResult>("POST", "/api/whatif", { worker, station }),
  checkin: (worker: string) => req<{ accounted: number }>("POST", "/api/emergency/checkin", { worker }),
  allClear: () => req<RestartPlan>("POST", "/api/emergency/all-clear", {}),
  chat: (message: string, history: { role: "user" | "assistant"; content: string }[], language: Language) =>
    req<ChatResponse>("POST", "/api/chat", { message, history, language }, 60000),
  confirmProposal: (id: string) => req<{ proposal: Proposal; applied: string[] }>("POST", `/api/proposals/${id}/confirm`, {}),
  rejectProposal: (id: string) => req<{ proposal: Proposal }>("POST", `/api/proposals/${id}/reject`, {}),
  handover: (language: Language) => req<HandoverResponse>("POST", "/api/handover", { language }, 60000),
};
