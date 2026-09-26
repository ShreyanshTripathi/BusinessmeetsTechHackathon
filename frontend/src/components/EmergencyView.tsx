import { useState } from 'react'
import type { RestartPlan } from '../api'
import type { EmergencyView as Emergency, ZoneView } from '../types'
import { Button } from './ui'

export default function EmergencyView({
  emergency, zones, onCheckin, onAllClear,
}: {
  emergency: Emergency
  zones: ZoneView[]
  onCheckin: (workerId: string) => void
  onAllClear: () => Promise<RestartPlan> | void
}) {
  const [confirming, setConfirming] = useState(false)
  const [plan, setPlan] = useState<RestartPlan | null>(null)
  const zone = zones.find((z) => z.id === emergency.zone)
  const total = emergency.people.length
  const missing = total - emergency.accounted

  const clear = async () => {
    const result = await onAllClear()
    if (result) setPlan(result)
  }

  return (
    <div className="flex h-full flex-col gap-4 rounded-xl border-2 border-red-500/70 bg-red-950/40 p-5">
      <div className="flex flex-wrap items-center gap-4">
        <span className="h-4 w-4 animate-pulse rounded-full bg-red-500" />
        <h1 className="text-2xl font-black tracking-tight text-red-100">EMERGENCY · ZONE {emergency.zone}</h1>
        <span className="font-mono text-red-200">{emergency.minutes} min</span>
        <span className="text-sm text-red-200/80">{emergency.reason}</span>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg bg-slate-950/70 p-4 ring-1 ring-red-500/30">
          <p className="text-xs uppercase tracking-widest text-slate-400">Accounted for</p>
          <p className={`mt-1 font-mono text-4xl font-bold ${missing ? 'text-red-300' : 'text-emerald-300'}`}>
            {emergency.accounted} / {total}
          </p>
          <p className="text-xs text-slate-400">{missing ? `${missing} not yet at ${emergency.assembly_point}` : 'Everyone is out'}</p>
        </div>
        <div className="rounded-lg bg-slate-950/70 p-4 ring-1 ring-red-500/30">
          <p className="text-xs uppercase tracking-widest text-slate-400">Evacuate via</p>
          <p className="mt-1 text-lg font-semibold text-slate-100">{emergency.exits.join(' · ')}</p>
          <p className="text-sm text-slate-300">Assembly point {emergency.assembly_point}</p>
        </div>
        <div className="rounded-lg bg-slate-950/70 p-4 ring-1 ring-red-500/30">
          <p className="text-xs uppercase tracking-widest text-slate-400">Fire wardens in zone</p>
          <p className="mt-1 text-lg font-semibold text-slate-100">{emergency.wardens.join(', ') || 'None: send nearest'}</p>
          {zone && (
            <p className="text-xs text-slate-400">
              {zone.sensors.filter((s) => s.value !== null && s.value >= s.warn).map((s) => `${s.id} ${s.value}${s.unit === '°C' ? '°C' : ''}`).join(' · ') || 'Sensors normal'}
            </p>
          )}
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs uppercase tracking-widest text-slate-400">Tap each person as they reach the assembly point</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {emergency.people.map((p) => (
            <button key={p.id} onClick={() => onCheckin(p.id)} disabled={p.accounted}
              aria-label={`${p.name}${p.accounted ? ' (accounted)' : ''}`}
              className={`rounded-lg px-3 py-2 text-left text-sm ring-1 transition ${p.accounted ? 'bg-emerald-900/40 text-emerald-200 ring-emerald-600/50' : 'bg-slate-900 text-slate-100 ring-slate-700 hover:ring-red-400'}`}>
              <span className="block font-medium">{p.name}</span>
              <span className="text-xs text-slate-400">{p.station ?? 'relief'}{p.fire_warden ? ' · warden' : ''}{p.accounted ? ' · ✓' : ''}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-auto flex flex-wrap items-center gap-3">
        {!confirming && !plan && <Button tone="primary" onClick={() => setConfirming(true)}>All clear</Button>}
        {confirming && !plan && (
          <>
            <span className="text-sm text-slate-200">Fire wardens confirmed the zone is safe?</span>
            <Button tone="primary" onClick={clear}>Confirm all clear</Button>
            <Button tone="ghost" onClick={() => setConfirming(false)}>Not yet</Button>
          </>
        )}
        {plan && (
          <div className="rounded-lg bg-slate-950/70 p-4 ring-1 ring-emerald-500/40">
            <p className="font-semibold text-emerald-300">Restart plan: recover {plan.cars_to_recover} cars</p>
            <ol className="mt-1 list-decimal pl-5 text-sm text-slate-200">
              {plan.steps.map((s) => <li key={s}>{s}</li>)}
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}
