import type { ModifiedAssignment } from '../api'
import type { Decision, Incident } from '../types'
import { modelName } from './ModelBox'

/** Lower-risk model predictions: kept out of the inbox, but visible so the supervisor can plan ahead. */
export default function ForecastList({ incidents, onDecision }: {
  incidents: Incident[]
  onDecision: (id: string, decision: Decision['decision'], reason: string, assignments?: ModifiedAssignment[]) => void
}) {
  const forecasts = incidents.filter((i) => i.predictions.length)
  if (!forecasts.length) return null
  return (
    <section className="mt-8">
      <h2 className="text-sm font-semibold text-slate-300">Model forecasts</h2>
      <p className="mb-3 text-xs text-slate-500">Lower-risk predictions from the random forests. Not urgent; useful for planning.</p>
      <ul aria-label="Model forecasts" className="divide-y divide-slate-800 rounded-2xl bg-slate-900 ring-1 ring-slate-800">
        {forecasts.map((inc) => {
          const p = inc.predictions[0]
          return (
            <li key={inc.id} aria-label={inc.title} className="flex items-start gap-4 px-4 py-3">
              <span className="mt-0.5 w-12 shrink-0 font-mono text-sm text-sky-300">{Math.round(p.risk * 100)}%</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-100">{inc.title}</p>
                <p className="mt-0.5 text-xs text-slate-400">{modelName(p.model)}: {p.explanation}</p>
              </div>
              <button onClick={() => onDecision(inc.id, 'accept', '', undefined)}
                className="shrink-0 rounded-lg px-2.5 py-1 text-xs text-slate-200 ring-1 ring-slate-700 hover:bg-slate-800">
                Act on it
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
