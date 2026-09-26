import { useState } from 'react'
import type { Explanation, Prediction } from '../types'

const MODEL_NAME: Record<string, string> = {
  staffing_model: 'Staffing model',
  assembly_model: 'Assembly model',
  safety_model: 'Safety model',
}

export function modelName(model: string): string {
  return MODEL_NAME[model] ?? model
}

/** What the random forest predicted for this incident and why; optionally re-explained by Claude. */
export default function ModelBox({ predictions, onExplain }: {
  predictions: Prediction[]
  onExplain?: () => Promise<Explanation[]>
}) {
  const [claude, setClaude] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  if (!predictions.length) return null

  const ask = async () => {
    if (!onExplain) return
    setBusy(true)
    try {
      const out = await onExplain()
      setClaude(Object.fromEntries(out.map((e) => [e.event_id, e.text])))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div role="group" aria-label="Model prediction" className="mt-4 rounded-xl bg-sky-500/5 p-3 ring-1 ring-sky-500/20">
      {predictions.map((p) => (
        <div key={p.event_id} className="text-sm">
          <p className="text-xs font-medium text-sky-300">
            {modelName(p.model)} · {Math.round(p.risk * 100)}% · random forest
          </p>
          <p className="mt-1 text-slate-300">{claude[p.event_id] ?? p.explanation}</p>
        </div>
      ))}
      {onExplain && Object.keys(claude).length === 0 && (
        <button onClick={ask} disabled={busy}
          className="mt-2 text-xs font-medium text-sky-300 hover:text-sky-200 disabled:opacity-50">
          {busy ? 'Asking Claude…' : 'Explain with Claude'}
        </button>
      )}
    </div>
  )
}
