import { apiUrl } from './config'
import type { Decision, Explanation, Incident, Language, ModelCard, Oversight, Proposal, Snapshot, WhatIfResult, Worker } from './types'

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(apiUrl(path), {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export interface ChatResponse {
  reply: string
  proposals: Proposal[]
  mode: 'claude' | 'offline'
}

export interface RestartPlan {
  zone: string
  duration_min: number
  cars_to_recover: number
  steps: string[]
}

export interface SimCommand {
  action: 'start' | 'pause' | 'step' | 'speed' | 'reset'
  minutes?: number
  speed?: number
  scenario?: 'demo' | 'quiet'
}

export type ModifiedAssignment = { worker: string; to_station: string | null; to_zone: string | null; kind: string; task: string }

export const api = {
  snapshot: () => request<Snapshot>('/api/snapshot'),
  workers: () => request<{ workers: Worker[]; stations: { id: string; zone: string; name: string }[] }>('/api/workers'),
  oversight: () => request<Oversight>('/api/oversight'),
  decide: (id: string, decision: Decision['decision'], reason = '', assignments?: ModifiedAssignment[]) =>
    request<Decision>(`/api/incidents/${id}/decision`, { decision, reason, assignments }),
  ackNotification: (id: string) => request(`/api/notifications/${id}/ack`, {}),
  ackEscalation: (id: string) => request(`/api/escalations/${id}/ack`, {}),
  chat: (message: string, history: { role: string; content: string }[], language: Language) =>
    request<ChatResponse>('/api/chat', { message, history, language }),
  confirmProposal: (id: string) => request<{ applied: string[] }>(`/api/proposals/${id}/confirm`, {}),
  rejectProposal: (id: string) => request(`/api/proposals/${id}/reject`, {}),
  handover: (language: Language) => request<{ text: string; mode: string }>('/api/handover', { language }),
  whatIf: (worker: string, station: string) => request<WhatIfResult>('/api/whatif', { worker, station }),
  sim: (cmd: SimCommand) => request('/api/sim', cmd),
  checkin: (worker: string) => request('/api/emergency/checkin', { worker }),
  allClear: () => request<RestartPlan>('/api/emergency/all-clear', {}),
  explain: (incidentId: string, language: Language = 'en') =>
    request<{ explanations: Explanation[] }>(`/api/incidents/${incidentId}/explain`, { language }),
  reportNearMiss: (text: string, zone: string, station: string | null) =>
    request<{ event: unknown; incident: Incident }>('/api/safety/report', { text, zone, station }),
  models: () => request<{ models: ModelCard[] }>('/api/models'),
}
