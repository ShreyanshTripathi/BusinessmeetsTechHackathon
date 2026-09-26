import { clockTime } from '../format'
import type { Escalation } from '../types'
import { Panel } from './ui'

function minutesBetween(a: string, b: string) {
  return Math.max(0, Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000))
}

export default function Escalations({ escalations, now, onAck }: { escalations: Escalation[]; now: string; onAck: (id: string) => void }) {
  const open = escalations.filter((e) => !e.acknowledged_at)
  return (
    <Panel title="Calls waiting for confirmation" action={<span className="text-xs text-slate-400">{open.length} open</span>}>
      {escalations.length === 0 && <p className="px-4 py-3 text-xs text-slate-500">No open calls.</p>}
      <ul>
        {escalations.map((e) => {
          const waited = minutesBetween(e.time, now)
          return (
            <li key={e.id} aria-label={`${e.team}: ${e.message}`} className="flex items-center gap-2 border-b border-slate-800/70 px-4 py-2">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-100"><b className="capitalize">{e.team}</b> · <span className="text-slate-300">{e.message}</span></p>
                {e.acknowledged_at ? (
                  <p className="text-xs text-emerald-400">Confirmed at {clockTime(e.acknowledged_at)}</p>
                ) : (
                  <p className={`text-xs ${e.reminders > 0 ? 'text-amber-300' : 'text-slate-400'}`}>
                    Waiting {waited} min{e.reminders > 0 ? ` · ${e.reminders} reminder${e.reminders > 1 ? 's' : ''} sent` : ''}
                  </p>
                )}
              </div>
              {!e.acknowledged_at && (
                <button onClick={() => onAck(e.id)} className="rounded-md px-2 py-1 text-xs text-slate-200 ring-1 ring-slate-700 hover:bg-slate-800">
                  Mark confirmed
                </button>
              )}
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
