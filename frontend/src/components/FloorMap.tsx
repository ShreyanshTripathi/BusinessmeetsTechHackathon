import { levelLabel } from '../format'
import type { StationView, ZoneView } from '../types'

const STATUS_STYLE: Record<StationView['status'], string> = {
  running: 'bg-emerald-500/10 ring-emerald-500/30 text-emerald-100',
  slowed: 'bg-amber-500/15 ring-amber-400/50 text-amber-100',
  starved: 'bg-amber-500/15 ring-amber-400/50 text-amber-100',
  stopped: 'bg-red-500/20 ring-red-500/60 text-red-100',
  halted: 'bg-red-900/40 ring-red-700 text-red-200',
}

const ALERT_RING: Record<string, string> = {
  critical: 'outline outline-2 outline-red-500',
  high: 'outline outline-2 outline-orange-500',
  medium: 'outline outline-1 outline-amber-400',
}

function statusText(s: StationView) {
  if (!s.operator && s.status !== 'halted') return 'no operator'
  return s.status
}

const LEGEND = [
  ['bg-emerald-500/40', 'Running'],
  ['bg-amber-500/50', 'Waiting / no operator'],
  ['bg-red-500/60', 'Stopped'],
]

export default function FloorMap({
  zones, stations, emergencyZone, selected, onSelect,
}: {
  zones: ZoneView[]
  stations: StationView[]
  emergencyZone: string | null
  selected: string | null
  onSelect: (id: string) => void
}) {
  const detail = stations.find((s) => s.id === selected)
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
        {zones.map((z) => (
          <section key={z.id} role="region" aria-label={z.name} data-emergency={emergencyZone === z.id ? 'true' : 'false'}
            className={`rounded-2xl p-4 ring-1 ${emergencyZone === z.id ? 'bg-red-950/40 ring-red-500' : 'bg-slate-900 ring-slate-800'}`}>
            <div className="mb-3 flex items-baseline justify-between">
              <h2 className="font-semibold text-slate-100">{z.name}</h2>
              <span className="text-sm text-slate-400">{z.people} people</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {stations.filter((s) => s.zone === z.id).map((s) => (
                <button key={s.id} onClick={() => onSelect(s.id)}
                  aria-label={`${s.id} ${s.name}: ${statusText(s)}`}
                  className={`rounded-xl px-2 py-2.5 text-left ring-1 transition hover:brightness-125 ${STATUS_STYLE[s.status]} ${s.alert ? ALERT_RING[s.alert] ?? '' : ''} ${selected === s.id ? 'ring-2 ring-sky-400' : ''}`}>
                  <span className="block whitespace-nowrap font-mono text-sm font-semibold">{s.id}</span>
                  <span className="block truncate text-xs opacity-75">{s.operator ? s.operator.name.split(' ')[0] : 'no operator'}</span>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
        {LEGEND.map(([color, label]) => (
          <span key={label} className="flex items-center gap-1.5"><span className={`h-3 w-3 rounded ${color}`} />{label}</span>
        ))}
        <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded outline outline-2 outline-orange-500" />Open incident</span>
        <span className="ml-auto">Cars flow A → D · click a station for details</span>
      </div>

      {detail && (
        <div className="rounded-2xl bg-slate-900 p-4 ring-1 ring-slate-800">
          <h2 className="font-semibold text-slate-100"><span className="font-mono">{detail.id}</span> · {detail.name}</h2>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm md:grid-cols-5">
            <div><dt className="text-xs text-slate-500">Status</dt><dd className="text-slate-200">{detail.status}</dd></div>
            <div><dt className="text-xs text-slate-500">Operator</dt><dd className="text-slate-200">{detail.operator ? `${detail.operator.name} (${levelLabel(detail.operator.level)})` : 'none'}</dd></div>
            <div><dt className="text-xs text-slate-500">Cycle / takt</dt><dd className="font-mono text-slate-200">{detail.cycle_time_s ?? '–'}s / {detail.takt_s}s</dd></div>
            <div><dt className="text-xs text-slate-500">Downtime</dt><dd className="font-mono text-slate-200">{detail.downtime_min} min</dd></div>
            <div><dt className="text-xs text-slate-500">Defects</dt><dd className="font-mono text-slate-200">{detail.defects}</dd></div>
          </dl>
        </div>
      )}
    </div>
  )
}
