import { useState } from 'react'
import { levelLabel } from '../format'
import type { StationView, WhatIfResult, Worker, ZoneView } from '../types'
import { Badge, Button, Panel } from './ui'

const LEVEL_TONE = ['red', 'amber', 'green', 'blue'] as const

export default function StaffingBoard({
  stations, zones, workers, onWhatIf,
}: {
  stations: StationView[]
  zones: ZoneView[]
  workers: Worker[]
  onWhatIf: (worker: string, station: string) => Promise<WhatIfResult>
}) {
  const [worker, setWorker] = useState('')
  const [station, setStation] = useState('')
  const [result, setResult] = useState<WhatIfResult | null>(null)
  const absent = workers.filter((w) => w.status === 'absent')
  const free = workers.filter((w) => w.status === 'present' && !w.station && w.role !== 'maintenance')

  return (
    <div className="grid min-h-0 gap-4 lg:grid-cols-[1fr_340px]">
      <Panel title="Stations">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-500">
            <tr><th className="px-4 py-2">Station</th><th>Operator</th><th>Level</th><th>Hours</th><th>Status</th></tr>
          </thead>
          <tbody>
            {stations.map((s) => {
              const w = s.operator ? workers.find((x) => x.id === s.operator!.id) : undefined
              return (
                <tr key={s.id} className="border-t border-slate-800/70">
                  <td className="px-4 py-1.5 font-mono text-slate-200">{s.id} <span className="font-sans text-xs text-slate-500">{s.name}</span></td>
                  <td className="text-slate-100">{s.operator ? s.operator.name : <span className="font-semibold text-red-300">No operator</span>}</td>
                  <td>{s.operator && <Badge tone={LEVEL_TONE[s.operator.level] ?? 'slate'}>{levelLabel(s.operator.level)}</Badge>}</td>
                  <td className="font-mono text-xs text-slate-400">{w ? w.hours_worked.toFixed(1) : ''}</td>
                  <td className="text-xs text-slate-400">{s.status}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Panel>

      <div className="flex min-h-0 flex-col gap-4">
        <Panel title="Safety roles per zone">
          <ul className="space-y-1 px-4 py-3 text-sm">
            {zones.map((z) => (
              <li key={z.id} className={z.fire_wardens.length ? 'text-slate-300' : 'font-semibold text-red-300'}>
                {z.fire_wardens.length
                  ? `${z.name}: warden ${z.fire_wardens.join(', ')} · first aid ${z.first_aiders.join(', ') || 'none'}`
                  : `${z.name}: no fire warden`}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="What if I move…">
          <div className="space-y-2 px-4 py-3">
            <select aria-label="Person" value={worker} onChange={(e) => setWorker(e.target.value)}
              className="w-full rounded-md bg-slate-950 px-2 py-1.5 text-sm text-slate-100 ring-1 ring-slate-700">
              <option value="">Person…</option>
              {workers.filter((w) => w.status === 'present').map((w) => (
                <option key={w.id} value={w.id}>{w.name} ({w.station ?? w.role})</option>
              ))}
            </select>
            <select aria-label="To station" value={station} onChange={(e) => setStation(e.target.value)}
              className="w-full rounded-md bg-slate-950 px-2 py-1.5 text-sm text-slate-100 ring-1 ring-slate-700">
              <option value="">To station…</option>
              {stations.map((s) => <option key={s.id} value={s.id}>{s.id} {s.name}</option>)}
            </select>
            <Button disabled={!worker || !station} onClick={async () => setResult(await onWhatIf(worker, station))}>Check</Button>
            {result && (
              <div className={`rounded-md p-2 text-sm ring-1 ${result.ok ? 'ring-emerald-600/60' : 'ring-amber-500/60'}`}>
                <p className="font-medium text-slate-100">{result.ok ? 'Looks fine' : 'Check before moving'}</p>
                <ul className="mt-1 list-disc pl-5 text-slate-300">
                  {result.warnings.map((w) => <li key={w}>{w}</li>)}
                  {result.benefits.map((b) => <li key={b} className="text-emerald-300">{b}</li>)}
                </ul>
              </div>
            )}
          </div>
        </Panel>

        <Panel title="People">
          <div className="space-y-2 px-4 py-3 text-sm">
            <p className="text-xs uppercase tracking-wider text-slate-500">Absent ({absent.length})</p>
            <p className="text-slate-300">{absent.map((w) => w.name).join(', ') || 'none'}</p>
            <p className="text-xs uppercase tracking-wider text-slate-500">Free relief ({free.length})</p>
            <p className="text-slate-300">{free.map((w) => w.name).join(', ') || 'none'}</p>
          </div>
        </Panel>
      </div>
    </div>
  )
}
