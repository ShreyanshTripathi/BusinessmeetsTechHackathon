// Mirrors backend/shiftloop/api/snapshot.py

export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical'
export type Agent = 'staffing' | 'assembly' | 'safety'
export type Language = 'en' | 'de' | 'pl'

export interface Assignment {
  worker: string
  worker_name: string
  kind: 'station' | 'relocate' | 'task'
  to_station: string | null
  to_zone: string | null
  task: string
  reason: string
}

export interface Recommendation {
  action: 'keep_running' | 'slow' | 'reroute' | 'stop' | 'emergency'
  scope: 'station' | 'zone' | 'section'
  target: string
  summary: string
  steps: string[]
  assignments: Assignment[]
  escalations: string[]
  hard_rule: string | null
}

export interface Incident {
  id: string
  title: string
  zone: string
  stations: string[]
  agents: string[]
  severity: Severity
  category: 'safety' | 'quality' | 'production' | 'staffing'
  confidence: number
  opened: string
  updated: string
  score: number
  status: 'open' | 'accepted' | 'dismissed' | 'resolved'
  visibility: 'active' | 'held'
  likely_cause: string | null
  evidence: string[]
  recommendation: Recommendation | null
}

export interface Operator {
  id: string
  name: string
  level: number
}

export interface StationView {
  id: string
  zone: string
  name: string
  status: 'running' | 'stopped' | 'starved' | 'slowed' | 'halted'
  safety_critical: boolean
  operator: Operator | null
  cycle_time_s: number | null
  takt_s: number
  downtime_min: number
  defects: number
  alert: Severity | null
}

export interface SensorView {
  id: string
  kind: 'smoke' | 'heat' | 'gas' | 'battery_temp'
  unit: string
  warn: number
  crit: number
  station: string | null
  value: number | null
}

export interface ZoneView {
  id: string
  name: string
  people: number
  fire_wardens: string[]
  first_aiders: string[]
  exits: string[]
  assembly_point: string
  sensors: SensorView[]
  alert: Severity | null
}

export interface Notification {
  id: string
  time: string
  level: 'critical' | 'warning' | 'info'
  title: string
  body: string
  incident_id: string | null
  acknowledged: boolean
}

export interface Escalation {
  id: string
  time: string
  team: string
  incident_id: string
  message: string
  acknowledged_at: string | null
  reminders: number
  last_reminder: string | null
}

export interface Proposal {
  id: string
  kind: 'assign' | 'incident_decision'
  description: string
  params: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'rejected'
}

export interface EmergencyPerson {
  id: string
  name: string
  station: string | null
  fire_warden: boolean
  accounted: boolean
}

export interface EmergencyView {
  zone: string
  started: string
  reason: string
  incident_id: string
  people: EmergencyPerson[]
  accounted: number
  exits: string[]
  assembly_point: string
  wardens: string[]
  minutes: number
}

export interface Kpis {
  time: string
  cars_built: number
  plan: number
  output_pct: number
  downtime_min: Record<string, number>
  downtime_total_min: number
  defects: number
  open_safety: number
  open_incidents: number
  impact: Record<string, number>
}

export interface SimStatus {
  running: boolean
  speed: number
  scenario: string
  vision: Record<string, string>
}

export interface Snapshot {
  clock: string
  sim: SimStatus
  mode: 'claude' | 'offline'
  zones: ZoneView[]
  stations: StationView[]
  incidents: { active: Incident[]; held: Incident[]; in_progress: Incident[] }
  notifications: Notification[]
  escalations: Escalation[]
  proposals: Proposal[]
  emergency: EmergencyView | null
  kpis: Kpis
  attention: { signals: number; events: number; incidents: number; active: number; held_back: number }
  expert_queue: { id: string; time: string; station: string; evidence: string[]; confidence: number }[]
}

export interface Worker {
  id: string
  name: string
  role: 'operator' | 'floater' | 'maintenance' | 'team_lead'
  home_zone: string
  zone: string
  station: string | null
  qualifications: Record<string, number>
  qual_expiry: Record<string, string>
  fire_warden: boolean
  first_aider: boolean
  status: 'present' | 'absent' | 'break'
  hours_worked: number
  busy_with: string | null
  languages: string[]
}

export interface WhatIfResult {
  worker: string
  worker_name: string
  from_station: string | null
  to_station: string
  ok: boolean
  warnings: string[]
  benefits: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  proposals?: Proposal[]
}

export interface Decision {
  id: string
  time: string
  incident_id: string
  incident_title: string
  recommended: string
  decision: 'accept' | 'modify' | 'dismiss'
  reason: string
  applied: string[]
  agents: string[]
  decided_by: string
}

export interface Oversight {
  decisions: { total: number; accept: number; modify: number; dismiss: number }
  override_rate: number
  human_decided_pct: number
  agents: Record<string, { events: number; incidents: number; decisions: number; accepted: number; overridden: number }>
  expert_queue: number
  attention: Snapshot['attention']
  log: Decision[]
  data_use: Record<string, { uses: string[]; purpose: string; never: string[] }>
  works_council: Record<string, boolean | string>
}
