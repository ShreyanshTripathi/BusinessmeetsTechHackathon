import type { SimCommand } from '../api'
import { clockTime } from '../format'
import type { Snapshot } from '../types'

export default function TopBar({ snapshot, onSim }: { snapshot: Snapshot; onSim: (cmd: SimCommand) => void }) {
  const k = snapshot.kpis
  const running = snapshot.sim.running
  const outputTone = k.output_pct >= 95 ? 'text-emerald-300' : k.output_pct >= 85 ? 'text-amber-300' : 'text-red-300'
  return (
    <header className="flex items-center gap-6 border-b border-slate-800 px-6 py-3">
      <span className="font-mono text-2xl font-semibold text-slate-50">{clockTime(snapshot.clock)}</span>
      <div>
        <p className="text-[11px] uppercase tracking-widest text-slate-500">Cars / plan</p>
        <p className={`font-mono text-sm font-semibold ${outputTone}`}>{k.cars_built} / {k.plan}</p>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <span className="text-xs text-slate-500">Simulation</span>
        {running ? (
          <button aria-label="Pause" onClick={() => onSim({ action: 'pause' })}
            className="rounded-lg px-3 py-1.5 text-sm text-slate-100 ring-1 ring-slate-700 hover:bg-slate-800">❚❚</button>
        ) : (
          <button aria-label="Play" onClick={() => onSim({ action: 'start' })}
            className="rounded-lg bg-emerald-500 px-3 py-1.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400">▶</button>
        )}
        <button onClick={() => onSim({ action: 'step', minutes: 15 })}
          className="rounded-lg px-3 py-1.5 text-sm text-slate-200 ring-1 ring-slate-700 hover:bg-slate-800">+15 min</button>
        <select aria-label="Speed" value={snapshot.sim.speed} onChange={(e) => onSim({ action: 'speed', speed: Number(e.target.value) })}
          className="rounded-lg bg-slate-900 px-2 py-1.5 text-sm text-slate-200 ring-1 ring-slate-700">
          {[1, 2, 5, 10, 30].map((s) => <option key={s} value={s}>{s}x speed</option>)}
        </select>
        <button onClick={() => onSim({ action: 'reset', scenario: 'demo' })}
          className="rounded-lg px-3 py-1.5 text-sm text-slate-400 hover:bg-slate-800">Reset</button>
      </div>
    </header>
  )
}
