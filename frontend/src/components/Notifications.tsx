import { clockTime, sortNotifications } from '../format'
import type { Notification } from '../types'
import { Panel } from './ui'

const DOT = { critical: 'bg-red-500', warning: 'bg-amber-400', info: 'bg-sky-400' }

export default function Notifications({ notifications, onAck }: { notifications: Notification[]; onAck: (id: string) => void }) {
  const sorted = sortNotifications(notifications)
  const fresh = notifications.filter((n) => !n.acknowledged).length
  return (
    <Panel title="Notifications" action={<span className="text-xs text-slate-400">{fresh} new</span>}>
      <ul>
        {sorted.slice(0, 15).map((n) => (
          <li key={n.id} data-level={n.level}
            className={`flex items-start gap-2 border-b border-slate-800/70 px-4 py-2 ${n.acknowledged ? 'opacity-50' : ''}`}>
            <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${DOT[n.level]} ${!n.acknowledged && n.level === 'critical' ? 'animate-pulse' : ''}`} />
            <div className="min-w-0 flex-1">
              <p className="text-sm leading-snug text-slate-100">{n.title}</p>
              {n.body && <p className="truncate text-xs text-slate-400">{n.body}</p>}
            </div>
            <span className="font-mono text-[11px] text-slate-500">{clockTime(n.time)}</span>
            {!n.acknowledged && (
              <button onClick={() => onAck(n.id)} aria-label="Acknowledge"
                className="rounded px-1.5 text-xs text-slate-400 ring-1 ring-slate-700 hover:bg-slate-800">✓</button>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  )
}
