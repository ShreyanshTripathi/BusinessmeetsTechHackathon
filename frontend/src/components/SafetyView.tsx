import { useState } from 'react'
import type { Incident, SensorView, ZoneView } from '../types'
import { modelName } from './ModelBox'

const SENSOR_NAME: Record<SensorView['kind'], string> = {
  smoke: 'Smoke',
  heat: 'Heat',
  gas: 'CO gas',
  battery_temp: 'Battery temp',
}

function sensorState(s: SensorView): 'normal' | 'warning' | 'critical' {
  if (s.value === null) return 'normal'
  if (s.value >= s.crit) return 'critical'
  if (s.value >= s.warn) return 'warning'
  return 'normal'
}

const STATE_STYLE = {
  normal: 'text-slate-300',
  warning: 'text-amber-300',
  critical: 'text-red-300 font-semibold',
}

const STATIONS_BY_ZONE: Record<string, string[]> = Object.fromEntries(
  ['A', 'B', 'C', 'D'].map((z, i) => [z, Array.from({ length: 6 }, (_, k) => `S${String(i * 6 + k + 1).padStart(2, '0')}`)]),
)

function NearMissForm({ onReport }: { onReport: (text: string, zone: string, station: string | null) => Promise<Incident> }) {
  const [text, setText] = useState('')
  const [zone, setZone] = useState('A')
  const [station, setStation] = useState('')
  const [result, setResult] = useState<Incident | null>(null)
  const [busy, setBusy] = useState(false)

  const send = async () => {
    setBusy(true)
    try {
      setResult(await onReport(text.trim(), zone, station || null))
      setText('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-2xl bg-slate-900 p-5 ring-1 ring-slate-800">
      <h2 className="font-semibold text-slate-100">Report a near miss</h2>
      <p className="text-xs text-slate-500">The safety model rates how serious it could have been. Unsure ratings go to the safety expert. Describe the event, not the person.</p>
      <label className="mt-3 block text-xs text-slate-400">What happened
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3}
          className="mt-1 w-full rounded-lg bg-slate-950 p-3 text-sm text-slate-100 ring-1 ring-slate-700 focus:outline-none focus:ring-sky-500" />
      </label>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <label className="text-xs text-slate-400">Zone
          <select value={zone} onChange={(e) => { setZone(e.target.value); setStation('') }}
            className="ml-2 rounded-lg bg-slate-950 px-2 py-1.5 text-sm text-slate-100 ring-1 ring-slate-700">
            {['A', 'B', 'C', 'D'].map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </label>
        <label className="text-xs text-slate-400">Station
          <select value={station} onChange={(e) => setStation(e.target.value)}
            className="ml-2 rounded-lg bg-slate-950 px-2 py-1.5 text-sm text-slate-100 ring-1 ring-slate-700">
            <option value="">whole zone</option>
            {STATIONS_BY_ZONE[zone].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <button onClick={send} disabled={busy || text.trim().length < 3}
          className="ml-auto rounded-lg bg-emerald-500 px-3 py-1.5 text-sm font-semibold text-slate-950 disabled:opacity-40">
          {busy ? 'Rating…' : 'Send report'}
        </button>
      </div>
      {result && (
        <p className="mt-3 text-sm text-slate-300">Report sent: <span className="text-slate-100">{result.title}</span>. {result.predictions[0]?.explanation}</p>
      )}
    </div>
  )
}

export default function SafetyView({ zones, emergencyZone, reports = [], onReport }: {
  zones: ZoneView[]
  emergencyZone: string | null
  reports?: Incident[]
  onReport?: (text: string, zone: string, station: string | null) => Promise<Incident>
}) {
  return (
    <div className="space-y-6">
    {onReport && (
      <div className="grid gap-4 lg:grid-cols-2">
        <NearMissForm onReport={onReport} />
        <div className="rounded-2xl bg-slate-900 p-5 ring-1 ring-slate-800">
          <h2 className="font-semibold text-slate-100">Near-miss reports this shift</h2>
          {reports.length === 0 ? <p className="mt-2 text-sm text-slate-500">None yet.</p> : (
            <ul aria-label="Near-miss reports" className="mt-2 space-y-3">
              {reports.map((r) => (
                <li key={r.id} className="text-sm">
                  <p className="font-medium text-slate-100">{r.title}</p>
                  <p className="text-xs text-slate-400">{modelName(r.predictions[0].model)}: {r.predictions[0].explanation}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    )}
    <div className="grid gap-4 md:grid-cols-2">
      {zones.map((z) => (
        <section key={z.id} role="region" aria-label={z.name} data-emergency={emergencyZone === z.id ? 'true' : 'false'}
          className={`rounded-2xl p-5 ring-1 ${emergencyZone === z.id ? 'bg-red-950/40 ring-red-500' : 'bg-slate-900 ring-slate-800'}`}>
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-semibold text-slate-50">{z.name}</h2>
            <span className="text-sm text-slate-400">{z.people} people</span>
          </div>

          <dl className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Fire warden</dt>
              <dd className={z.fire_wardens.length ? 'text-slate-200' : 'font-semibold text-red-300'}>
                {z.fire_wardens.length ? z.fire_wardens.join(', ') : 'No fire warden'}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">First aider</dt>
              <dd className={z.first_aiders.length ? 'text-slate-200' : 'text-amber-300'}>
                {z.first_aiders.length ? z.first_aiders.join(', ') : 'None'}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Exits</dt>
              <dd className="text-slate-200">{z.exits.join(' · ')}</dd>
            </div>
          </dl>

          <div className="mt-4 grid grid-cols-2 gap-2">
            {z.sensors.map((s) => {
              const state = sensorState(s)
              return (
                <div key={s.id} data-state={state}
                  className={`rounded-lg px-3 py-2 ${state === 'normal' ? 'bg-slate-950/60' : state === 'warning' ? 'bg-amber-500/10 ring-1 ring-amber-500/40' : 'bg-red-500/15 ring-1 ring-red-500/60'}`}>
                  <p className="text-xs text-slate-500">{SENSOR_NAME[s.kind]}{s.station ? ` · ${s.station}` : ''}</p>
                  <p className={`font-mono text-base ${STATE_STYLE[state]}`}>
                    {s.value === null ? '–' : s.value.toFixed(s.kind === 'smoke' ? 1 : 0)} <span className="text-xs text-slate-500">{s.unit}</span>
                  </p>
                </div>
              )
            })}
          </div>
        </section>
      ))}
    </div>
    </div>
  )
}
