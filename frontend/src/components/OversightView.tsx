import { agentLabel, clockTime } from '../format'
import type { ModelCard, Oversight } from '../types'
import { modelName } from './ModelBox'
import { Badge, Panel } from './ui'

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg bg-slate-900/60 p-4 ring-1 ring-slate-800">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-3xl font-semibold text-slate-50">{value}</p>
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
    </div>
  )
}

const DECISION_TONE = { accept: 'green', modify: 'amber', dismiss: 'slate' } as const

function headline(card: ModelCard): string {
  const m = card.metrics
  if (card.model === 'safety_model') return `accuracy ${m.accuracy} (was ${m.baseline_logreg_accuracy}), high-potential caught ${m.high_recall} (was ${m.baseline_logreg_high_recall})`
  return `ROC AUC ${m.roc_auc} (replaced model ${m.baseline_logreg_roc_auc})`
}

export default function OversightView({ data, models = [] }: { data: Oversight; models?: ModelCard[] }) {
  return (
    <div className="grid min-h-0 gap-4 lg:grid-cols-[1fr_380px]">
      <div className="flex min-h-0 flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Decisions by humans" value={`${data.human_decided_pct}%`} hint={`${data.decisions.total} decisions this shift`} />
          <Stat label="Override rate" value={`${Math.round(data.override_rate * 100)}%`} hint="changed or dismissed" />
          <Stat label="Signals → decisions" value={`${data.attention.signals}`} hint={`became ${data.attention.incidents} incidents`} />
          <Stat label="Expert queue" value={`${data.expert_queue}`} hint="uncertain inspections" />
        </div>
        <Panel title="Decision log">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="px-4 py-2">Time</th><th>Incident</th><th>Decision</th><th>Applied / reason</th><th>By</th></tr>
            </thead>
            <tbody>
              {data.log.map((d) => (
                <tr key={d.id} className="border-t border-slate-800/70 align-top">
                  <td className="px-4 py-1.5 font-mono text-xs text-slate-400">{clockTime(d.time)}</td>
                  <td className="text-slate-200">{d.incident_title}</td>
                  <td><Badge tone={DECISION_TONE[d.decision]}>{d.decision}</Badge></td>
                  <td className="text-xs text-slate-400">{[...d.applied, d.reason && `reason: ${d.reason}`].filter(Boolean).join(' · ')}</td>
                  <td className="text-xs text-slate-500">{d.decided_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
      <div className="flex min-h-0 flex-col gap-4">
        {models.length > 0 && (
          <Panel title="Models">
            <ul aria-label="Models" className="space-y-3 px-4 py-3 text-xs">
              {models.map((c) => (
                <li key={c.model}>
                  <p className="font-semibold text-slate-200">{modelName(c.model)}</p>
                  <p className="text-slate-400">{c.algorithm}</p>
                  <p className="text-slate-300">{headline(c)}</p>
                  <p className="text-slate-500">Limits: {c.limits}</p>
                </li>
              ))}
            </ul>
          </Panel>
        )}
        <Panel title="Works council view">
          <ul className="space-y-1.5 px-4 py-3 text-sm text-slate-200">
            <li>✓ No individual performance scoring</li>
            <li>✓ Every action decided by a human</li>
            <li>✓ Cameras: zone-level detections, no identities</li>
            <li>✓ Full decision log kept</li>
          </ul>
        </Panel>
        <Panel title="Agents">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr><th className="px-4 py-2">Agent</th><th>Events</th><th>Accepted</th><th>Overridden</th></tr>
            </thead>
            <tbody>
              {Object.entries(data.agents).map(([name, a]) => (
                <tr key={name} className="border-t border-slate-800/70">
                  <td className="px-4 py-1.5 text-slate-200">{agentLabel(name)}</td>
                  <td className="font-mono text-slate-300">{a.events}</td>
                  <td className="font-mono text-emerald-300">{a.accepted}</td>
                  <td className="font-mono text-amber-300">{a.overridden}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title="Data each agent uses">
          <div className="space-y-3 px-4 py-3 text-xs">
            {Object.entries(data.data_use).map(([name, d]) => (
              <div key={name}>
                <p className="font-semibold text-slate-200">{agentLabel(name)}</p>
                <p className="text-slate-400">Uses: {d.uses.join(', ')}</p>
                <p className="text-slate-500">Never: {d.never.join(', ')}</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}
