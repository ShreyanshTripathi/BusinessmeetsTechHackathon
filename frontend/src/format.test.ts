import { actionLabel, agentLabel, clockTime, levelLabel, severityTone, sortNotifications } from './format'
import type { Notification } from './types'

test('clockTime shows HH:MM from an ISO timestamp', () => {
  expect(clockTime('2026-10-01T10:16:00')).toBe('10:16')
})

test('severity tones escalate from neutral to red', () => {
  expect(severityTone('critical')).toBe('red')
  expect(severityTone('high')).toBe('orange')
  expect(severityTone('medium')).toBe('amber')
  expect(severityTone('low')).toBe('slate')
  expect(severityTone(null)).toBe('slate')
})

test('agent labels are human readable', () => {
  expect(agentLabel('safety')).toBe('Fire & Safety')
  expect(agentLabel('assembly')).toBe('Assembly')
  expect(agentLabel('staffing')).toBe('Staffing')
})

test('qualification levels have names', () => {
  expect(levelLabel(0)).toBe('untrained')
  expect(levelLabel(1)).toBe('trainee')
  expect(levelLabel(2)).toBe('qualified')
  expect(levelLabel(3)).toBe('trainer')
})

test('recommendation actions read as instructions', () => {
  expect(actionLabel('emergency')).toBe('EMERGENCY')
  expect(actionLabel('stop')).toBe('Stop')
  expect(actionLabel('keep_running')).toBe('Keep running')
})

test('notifications sort unacknowledged critical first, then newest', () => {
  const n = (id: string, level: Notification['level'], time: string, acknowledged = false): Notification => ({
    id, level, time, title: id, body: '', incident_id: null, acknowledged,
  })
  const sorted = sortNotifications([
    n('a', 'info', '2026-10-01T10:00:00'),
    n('b', 'critical', '2026-10-01T09:00:00'),
    n('c', 'warning', '2026-10-01T10:05:00'),
    n('d', 'critical', '2026-10-01T10:10:00', true),
  ])
  expect(sorted.map((x) => x.id)).toEqual(['b', 'c', 'a', 'd'])
})
