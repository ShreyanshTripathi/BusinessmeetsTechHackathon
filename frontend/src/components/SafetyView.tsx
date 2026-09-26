import type { SensorView, ZoneView } from '../types'

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

export default function SafetyView({ zones, emergencyZone }: { zones: ZoneView[]; emergencyZone: string | null }) {
  return (
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
  )
}
