import { useEffect, useState, type ReactNode } from 'react'
import { api } from './api'
import ChatPanel from './components/ChatPanel'
import EmergencyView from './components/EmergencyView'
import Escalations from './components/Escalations'
import FloorMap from './components/FloorMap'
import HandoverView from './components/HandoverView'
import Notifications from './components/Notifications'
import OversightView from './components/OversightView'
import PriorityInbox from './components/PriorityInbox'
import SafetyView from './components/SafetyView'
import StaffingBoard from './components/StaffingBoard'
import TopBar from './components/TopBar'
import type { Oversight, Snapshot, Worker } from './types'
import { useSnapshot } from './useSnapshot'

type Section = 'now' | 'line' | 'people' | 'safety' | 'alerts' | 'copilot' | 'oversight' | 'handover'

const PAGES: Record<Section, { label: string; icon: string; title: string; subtitle: string }> = {
  now: { label: 'Now', icon: '◉', title: 'Decisions waiting for you', subtitle: 'The few things that need a supervisor decision, most urgent first.' },
  line: { label: 'Line', icon: '▦', title: 'Line', subtitle: 'Every station in the section, live.' },
  people: { label: 'People', icon: '◍', title: 'People', subtitle: 'Who is where, qualifications, and what-if checks before moving anyone.' },
  safety: { label: 'Safety', icon: '△', title: 'Safety', subtitle: 'Sensors, fire wardens, first aiders and exits per zone.' },
  alerts: { label: 'Alerts', icon: '◔', title: 'Alerts', subtitle: 'Notifications and calls that still need a confirmation.' },
  copilot: { label: 'Copilot', icon: '✦', title: 'Copilot', subtitle: 'Ask anything about the shift. Suggested changes need your confirmation.' },
  oversight: { label: 'Oversight', icon: '◇', title: 'Oversight', subtitle: 'Every AI recommendation and every human decision.' },
  handover: { label: 'Handover', icon: '⇥', title: 'Handover', subtitle: 'A draft for the next shift from everything that happened.' },
}

function useLoader<T>(load: () => Promise<T>, active: boolean, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  useEffect(() => {
    if (!active) return
    let live = true
    load().then((d) => live && setData(d)).catch(() => {})
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, ...deps])
  return data
}

function Sidebar({ section, onSelect, badges, emergency }: {
  section: Section
  onSelect: (s: Section) => void
  badges: Partial<Record<Section, number>>
  emergency: boolean
}) {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-slate-800 bg-slate-950 px-3 py-4">
      <div className="px-3 pb-6">
        <p className="text-sm font-black tracking-[0.25em] text-slate-100">SHIFTLOOP</p>
        <p className="text-xs text-slate-500">General Assembly · early shift</p>
      </div>
      <nav aria-label="Sections" className="flex flex-col gap-1">
        {(Object.keys(PAGES) as Section[]).map((id) => {
          const page = PAGES[id]
          const count = badges[id] ?? 0
          const current = section === id
          const urgent = id === 'now' && emergency
          return (
            <button key={id} onClick={() => onSelect(id)} aria-current={current ? 'page' : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition ${current ? 'bg-slate-800 text-slate-50' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}>
              <span aria-hidden="true" className="w-4 text-center text-slate-500">{page.icon}</span>
              <span className="flex-1">{page.label}</span>
              {count > 0 && (
                <span className={`rounded-full px-2 text-xs font-semibold ${urgent ? 'bg-red-500 text-white' : 'bg-slate-700 text-slate-200'}`}>{count}</span>
              )}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}

function Page({ section, children }: { section: Section; children: ReactNode }) {
  const page = PAGES[section]
  const wide = section === 'line' || section === 'people' || section === 'oversight' || section === 'safety'
  return (
    <div className={`mx-auto flex h-full flex-col px-6 py-6 ${wide ? 'max-w-7xl' : 'max-w-3xl'}`}>
      <h1 className="text-2xl font-semibold text-slate-50">{page.title}</h1>
      <p className="mb-6 mt-1 text-sm text-slate-500">{page.subtitle}</p>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  )
}

function Dashboard({ snapshot, refresh }: { snapshot: Snapshot; refresh: () => void }) {
  const [section, setSection] = useState<Section>('now')
  const [selected, setSelected] = useState<string | null>(null)
  const workers = useLoader(() => api.workers(), section === 'people', [snapshot.clock])
  const oversight = useLoader<Oversight>(() => api.oversight(), section === 'oversight', [snapshot.clock, snapshot.attention.incidents])

  const act = async <T,>(p: Promise<T>) => {
    const out = await p
    refresh()
    return out
  }

  const em = snapshot.emergency
  const badges: Partial<Record<Section, number>> = {
    now: em ? 1 : snapshot.incidents.active.length,
    safety: snapshot.kpis.open_safety,
    alerts: snapshot.notifications.filter((n) => !n.acknowledged).length + snapshot.escalations.filter((e) => !e.acknowledged_at).length,
  }

  const chat = (
    <ChatPanel mode={snapshot.mode} onSend={api.chat} onConfirm={(id) => act(api.confirmProposal(id))} onReject={(id) => act(api.rejectProposal(id))} />
  )

  let content: ReactNode
  if (section === 'now') {
    content = em ? (
      <EmergencyView emergency={em} zones={snapshot.zones} onCheckin={(id) => act(api.checkin(id))} onAllClear={() => act(api.allClear())} />
    ) : (
      <PriorityInbox
        active={snapshot.incidents.active}
        held={snapshot.incidents.held}
        inProgress={snapshot.incidents.in_progress}
        attention={snapshot.attention}
        onDecision={(id, d, reason, assignments) => act(api.decide(id, d, reason, assignments))}
      />
    )
  } else if (section === 'line') {
    content = <FloorMap zones={snapshot.zones} stations={snapshot.stations} emergencyZone={em?.zone ?? null} selected={selected} onSelect={setSelected} />
  } else if (section === 'people') {
    content = workers
      ? <StaffingBoard stations={snapshot.stations} zones={snapshot.zones} workers={workers.workers as Worker[]} onWhatIf={api.whatIf} />
      : <p className="text-sm text-slate-400">Loading…</p>
  } else if (section === 'safety') {
    content = <SafetyView zones={snapshot.zones} emergencyZone={em?.zone ?? null} />
  } else if (section === 'alerts') {
    content = (
      <div className="flex flex-col gap-6">
        <Notifications notifications={snapshot.notifications} onAck={(id) => act(api.ackNotification(id))} />
        <Escalations escalations={snapshot.escalations} now={snapshot.clock} onAck={(id) => act(api.ackEscalation(id))} />
      </div>
    )
  } else if (section === 'copilot') {
    content = <div className="h-[calc(100vh-14rem)]">{chat}</div>
  } else if (section === 'oversight') {
    content = oversight ? <OversightView data={oversight} /> : <p className="text-sm text-slate-400">Loading…</p>
  } else {
    content = <div className="h-[calc(100vh-14rem)]"><HandoverView onGenerate={api.handover} /></div>
  }

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      <Sidebar section={section} onSelect={setSection} badges={badges} emergency={!!em} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar snapshot={snapshot} onSim={(cmd) => act(api.sim(cmd))} />
        {em && section !== 'now' && (
          <div role="alert" className="flex items-center gap-3 bg-red-600 px-6 py-2 text-sm font-semibold text-white">
            <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
            Emergency in zone {em.zone}: {em.reason}
            <button onClick={() => setSection('now')} className="ml-auto rounded bg-white/20 px-2 py-0.5 text-xs hover:bg-white/30">Open emergency view</button>
          </div>
        )}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Page section={section}>{content}</Page>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const { snapshot, connected, refresh } = useSnapshot()
  if (!snapshot) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-400">
        {connected ? 'Loading…' : 'Connecting to the ShiftLoop backend on :8000…'}
      </div>
    )
  }
  return <Dashboard snapshot={snapshot} refresh={refresh} />
}
