import { useState } from 'react'
import type { ModifiedAssignment } from '../api'
import { actionLabel, agentLabel, clockTime, severityTone, TONE_BORDER } from '../format'
import type { Decision, Explanation, Incident, Snapshot } from '../types'
import ModelBox from './ModelBox'
import { Button } from './ui'

type OnDecision = (id: string, decision: Decision['decision'], reason: string, assignments?: ModifiedAssignment[]) => void
type OnExplain = (id: string) => Promise<Explanation[]>

const RULES: Record<string, string> = {
  safety_stop: 'Safety rule · cannot be dismissed',
  quality_spread: 'Quality rule · defect may spread',
}

const SEVERITY_TEXT = {
  red: 'text-red-300', orange: 'text-orange-300', amber: 'text-amber-200', blue: 'text-sky-300', green: 'text-emerald-300', slate: 'text-slate-400',
}

function IncidentCard({ inc, onDecision, onExplain }: { inc: Incident; onDecision: OnDecision; onExplain?: OnExplain }) {
  const [mode, setMode] = useState<'view' | 'dismiss' | 'change'>('view')
  const [reason, setReason] = useState('')
  const rec = inc.recommendation
  const [kept, setKept] = useState<Set<string>>(() => new Set(rec?.assignments.map((a) => a.worker) ?? []))
  const tone = severityTone(inc.severity)
  const safetyLocked = rec?.hard_rule === 'safety_stop'
  const titleId = `inc-${inc.id}`
  const stop = rec?.action === 'emergency' || rec?.action === 'stop'

  const toggle = (worker: string) =>
    setKept((prev) => {
      const next = new Set(prev)
      if (next.has(worker)) next.delete(worker)
      else next.add(worker)
      return next
    })

  const sendChange = () => {
    const assignments = (rec?.assignments ?? [])
      .filter((a) => kept.has(a.worker))
      .map((a) => ({ worker: a.worker, to_station: a.to_station, to_zone: a.to_zone, kind: a.kind, task: a.task }))
    onDecision(inc.id, 'modify', reason, assignments)
  }

  return (
    <article aria-labelledby={titleId} className={`rounded-2xl border-l-4 bg-slate-900 p-5 ring-1 ring-slate-800 ${TONE_BORDER[tone]}`}>
      <p className="text-xs text-slate-500">
        <span className={`font-semibold uppercase ${SEVERITY_TEXT[tone]}`}>{inc.severity}</span>
        {' · '}{clockTime(inc.opened)} · Zone {inc.zone} · from{' '}
        {inc.agents.map((a, i) => (
          <span key={a}>{i > 0 && ' + '}<span className="text-slate-300">{agentLabel(a)}</span></span>
        ))}
      </p>
      <h3 id={titleId} className="mt-1 text-lg font-semibold leading-snug text-slate-50">{inc.title}</h3>
      {inc.likely_cause && <p className="mt-1 text-sm text-sky-300">{inc.likely_cause}</p>}

      {rec && (
        <div className="mt-4">
          <p className="text-sm">
            <span className={`mr-2 font-bold ${stop ? 'text-red-400' : 'text-emerald-400'}`}>{actionLabel(rec.action)}</span>
            <span className="text-slate-100">{rec.summary}</span>
          </p>
          {rec.hard_rule && <p className="mt-1 text-xs font-medium text-red-300">{RULES[rec.hard_rule] ?? rec.hard_rule}</p>}
          <ol className="mt-3 space-y-1.5 text-sm text-slate-300">
            {rec.steps.map((s, i) => (
              <li key={i} className="flex gap-3"><span className="w-4 shrink-0 text-right font-mono text-slate-600">{i + 1}</span><span>{s}</span></li>
            ))}
          </ol>
          {rec.escalations.length > 0 && <p className="mt-2 text-xs text-slate-500">Calls {rec.escalations.join(', ')}</p>}
        </div>
      )}

      <ModelBox predictions={inc.predictions ?? []} onExplain={onExplain ? () => onExplain(inc.id) : undefined} />

      <details className="mt-3 text-xs text-slate-500">
        <summary className="cursor-pointer select-none hover:text-slate-300">Why? ({inc.evidence.length} signals)</summary>
        <ul className="mt-1 list-disc space-y-0.5 pl-5">
          {inc.evidence.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      </details>

      {mode === 'view' && (
        <div className="mt-4 flex gap-2">
          <Button tone="primary" onClick={() => onDecision(inc.id, 'accept', '', undefined)}>Accept</Button>
          <Button onClick={() => setMode('change')} disabled={!rec?.assignments.length}>Change</Button>
          <Button tone="ghost" onClick={() => setMode('dismiss')} disabled={safetyLocked}
            title={safetyLocked ? 'Safety stops cannot be dismissed' : undefined}>
            Dismiss
          </Button>
        </div>
      )}

      {mode === 'change' && rec && (
        <div className="mt-4 space-y-2 rounded-xl bg-slate-950/60 p-3">
          <p className="text-xs text-slate-400">Keep the moves you want:</p>
          {rec.assignments.map((a) => (
            <label key={a.worker} className="flex items-center gap-2 text-sm text-slate-200">
              <input type="checkbox" checked={kept.has(a.worker)} onChange={() => toggle(a.worker)} aria-label={`${a.worker_name}: ${a.task}`} />
              <span><b>{a.worker_name}</b>: {a.task}</span>
            </label>
          ))}
          <ReasonInput value={reason} onChange={setReason} />
          <div className="flex gap-2">
            <Button tone="primary" disabled={!reason.trim()} onClick={sendChange}>Send change</Button>
            <Button tone="ghost" onClick={() => setMode('view')}>Cancel</Button>
          </div>
        </div>
      )}

      {mode === 'dismiss' && (
        <div className="mt-4 space-y-2">
          <ReasonInput value={reason} onChange={setReason} />
          <div className="flex gap-2">
            <Button tone="danger" disabled={!reason.trim()} onClick={() => onDecision(inc.id, 'dismiss', reason, undefined)}>Confirm dismiss</Button>
            <Button tone="ghost" onClick={() => setMode('view')}>Cancel</Button>
          </div>
        </div>
      )}
    </article>
  )
}

function ReasonInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="block text-xs text-slate-400">
      Reason (goes into the handover)
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-slate-700 focus:outline-none focus:ring-sky-500"
      />
    </label>
  )
}

export default function PriorityInbox({
  active, held, inProgress, attention, onDecision, onExplain,
}: {
  active: Incident[]
  held: Incident[]
  inProgress: Incident[]
  attention: Snapshot['attention']
  onDecision: OnDecision
  onExplain?: OnExplain
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        <span className="font-mono text-slate-300">{attention.signals} signals</span> from the line, filtered to{' '}
        <span className="font-mono text-slate-300">{active.length} decisions</span> · {held.length} lower-priority held back
      </p>
      {active.length === 0 ? (
        <div className="rounded-2xl bg-slate-900 px-6 py-16 text-center ring-1 ring-slate-800">
          <p className="text-lg text-slate-200">All clear</p>
          <p className="mt-1 text-sm text-slate-500">Nothing needs you right now.</p>
        </div>
      ) : (
        active.map((inc) => <IncidentCard key={inc.id} inc={inc} onDecision={onDecision} onExplain={onExplain} />)
      )}
      {inProgress.length > 0 && (
        <p className="text-xs text-slate-500">In progress: {inProgress.map((i) => i.title).join(' · ')}</p>
      )}
    </div>
  )
}
