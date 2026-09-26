import type { Notification, Recommendation, Severity } from './types'

export type Tone = 'red' | 'orange' | 'amber' | 'blue' | 'green' | 'slate'

export function clockTime(iso: string): string {
  return iso.slice(11, 16)
}

export function severityTone(sev: Severity | null | undefined): Tone {
  switch (sev) {
    case 'critical':
      return 'red'
    case 'high':
      return 'orange'
    case 'medium':
      return 'amber'
    default:
      return 'slate'
  }
}

const AGENTS: Record<string, string> = { safety: 'Fire & Safety', assembly: 'Assembly', staffing: 'Staffing', central: 'Central' }

export function agentLabel(agent: string): string {
  return AGENTS[agent] ?? agent
}

export function levelLabel(level: number): string {
  return ['untrained', 'trainee', 'qualified', 'trainer'][level] ?? `level ${level}`
}

const ACTIONS: Record<Recommendation['action'], string> = {
  emergency: 'EMERGENCY',
  stop: 'Stop',
  slow: 'Slow down',
  reroute: 'Reroute',
  keep_running: 'Keep running',
}

export function actionLabel(action: Recommendation['action']): string {
  return ACTIONS[action]
}

const LEVEL_RANK: Record<Notification['level'], number> = { critical: 0, warning: 1, info: 2 }

export function sortNotifications(list: Notification[]): Notification[] {
  return [...list].sort((a, b) => {
    if (a.acknowledged !== b.acknowledged) return a.acknowledged ? 1 : -1
    if (LEVEL_RANK[a.level] !== LEVEL_RANK[b.level]) return LEVEL_RANK[a.level] - LEVEL_RANK[b.level]
    return b.time.localeCompare(a.time)
  })
}

// Tailwind classes per tone (kept literal so Tailwind can see them)
export const TONE_BADGE: Record<Tone, string> = {
  red: 'bg-red-500/15 text-red-300 ring-1 ring-red-500/40',
  orange: 'bg-orange-500/15 text-orange-300 ring-1 ring-orange-500/40',
  amber: 'bg-amber-500/15 text-amber-200 ring-1 ring-amber-500/40',
  blue: 'bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/40',
  green: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/40',
  slate: 'bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30',
}

export const TONE_BORDER: Record<Tone, string> = {
  red: 'border-l-red-500',
  orange: 'border-l-orange-500',
  amber: 'border-l-amber-400',
  blue: 'border-l-sky-500',
  green: 'border-l-emerald-500',
  slate: 'border-l-slate-500',
}
