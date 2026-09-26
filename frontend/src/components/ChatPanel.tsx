import { useEffect, useRef, useState } from 'react'
import type { ChatResponse } from '../api'
import type { ChatMessage, Language, Proposal } from '../types'
import { Panel } from './ui'

const SUGGESTIONS = [
  'What needs my attention now?',
  'Who can cover S12?',
  'Is zone C safe?',
  'Which station caused the most downtime?',
  'Summarise the shift for the handover',
]

const SPEECH_LANG: Record<Language, string> = { en: 'en-US', de: 'de-DE', pl: 'pl-PL' }

type SpeechCtor = new () => {
  lang: string
  interimResults: boolean
  onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void
  onend: () => void
  start: () => void
}

function speechRecognition(): SpeechCtor | undefined {
  const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

type ProposalState = Proposal & { result?: string }
type Message = Omit<ChatMessage, 'proposals'> & { proposals?: ProposalState[] }

export default function ChatPanel({
  mode, onSend, onConfirm, onReject,
}: {
  mode: 'claude' | 'offline'
  onSend: (message: string, history: { role: string; content: string }[], language: Language) => Promise<ChatResponse>
  onConfirm: (id: string) => Promise<{ applied: string[] }> | void
  onReject: (id: string) => Promise<unknown> | void
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [language, setLanguage] = useState<Language>('en')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const Speech = speechRecognition()

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [messages])

  const send = async (text: string) => {
    const message = text.trim()
    if (!message || busy) return
    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    setMessages((m) => [...m, { role: 'user', content: message }])
    setInput('')
    setBusy(true)
    try {
      const res = await onSend(message, history, language)
      setMessages((m) => [...m, { role: 'assistant', content: res.reply, proposals: res.proposals }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', content: `Error: ${(e as Error).message}` }])
    } finally {
      setBusy(false)
    }
  }

  const settle = async (msgIndex: number, proposal: ProposalState, action: 'confirm' | 'reject') => {
    let result = 'Rejected'
    if (action === 'confirm') {
      const out = await onConfirm(proposal.id)
      result = `Applied: ${out?.applied?.join(', ') ?? 'done'}`
    } else {
      await onReject(proposal.id)
    }
    setMessages((ms) => ms.map((m, i) => i !== msgIndex ? m : {
      ...m,
      proposals: m.proposals?.map((p) => (p.id === proposal.id ? { ...p, status: action === 'confirm' ? 'confirmed' : 'rejected', result } : p)),
    }))
  }

  const listen = () => {
    if (!Speech) return
    const rec = new Speech()
    rec.lang = SPEECH_LANG[language]
    rec.interimResults = false
    rec.onresult = (e) => send(e.results[0][0].transcript)
    rec.onend = () => setListening(false)
    setListening(true)
    rec.start()
  }

  return (
    <Panel
      title="Copilot"
      className="h-full"
      action={
        <div className="flex items-center gap-2">
          <span className={`text-[11px] ${mode === 'claude' ? 'text-emerald-400' : 'text-amber-300'}`}>
            {mode === 'claude' ? 'Claude' : 'Offline mode'}
          </span>
          <select aria-label="Language" value={language} onChange={(e) => setLanguage(e.target.value as Language)}
            className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-200 ring-1 ring-slate-700">
            <option value="en">EN</option>
            <option value="de">DE</option>
            <option value="pl">PL</option>
          </select>
        </div>
      }
    >
      <div className="flex h-full flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
          {messages.length === 0 && (
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}
                  className="rounded-full px-2.5 py-1 text-xs text-slate-300 ring-1 ring-slate-700 hover:bg-slate-800">
                  {s}
                </button>
              ))}
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'flex justify-end' : ''}>
              <div className={`max-w-[92%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${m.role === 'user' ? 'bg-sky-600/30 text-sky-50' : 'bg-slate-800/70 text-slate-100'}`}>
                {m.content}
              </div>
              {m.proposals?.map((p) => (
                <div key={p.id} className="mt-2 rounded-lg border border-amber-500/40 bg-amber-500/5 p-2.5">
                  <p className="text-sm text-amber-100">{p.description}</p>
                  {p.status === 'pending' ? (
                    <div className="mt-2 flex gap-2">
                      <button onClick={() => settle(i, p, 'confirm')} className="rounded bg-emerald-500 px-2.5 py-1 text-xs font-semibold text-slate-950">Confirm</button>
                      <button onClick={() => settle(i, p, 'reject')} className="rounded px-2.5 py-1 text-xs text-slate-300 ring-1 ring-slate-600">Reject</button>
                    </div>
                  ) : (
                    <p className="mt-1 text-xs text-slate-400">{p.result}</p>
                  )}
                </div>
              ))}
            </div>
          ))}
          {busy && <p className="text-xs text-slate-500">Thinking…</p>}
          <div ref={end} />
        </div>
        <form className="flex gap-2 border-t border-slate-800 p-3" onSubmit={(e) => { e.preventDefault(); send(input) }}>
          <input aria-label="Ask the copilot" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about the shift…"
            className="min-w-0 flex-1 rounded-md bg-slate-950 px-3 py-2 text-sm text-slate-100 ring-1 ring-slate-700 focus:outline-none focus:ring-sky-500" />
          {Speech && (
            <button type="button" onClick={listen} aria-label="Speak"
              className={`rounded-md px-3 text-sm ring-1 ${listening ? 'bg-red-500/30 ring-red-400' : 'ring-slate-700 hover:bg-slate-800'}`}>
              🎙
            </button>
          )}
          <button type="submit" disabled={busy} className="rounded-md bg-sky-500 px-3 text-sm font-semibold text-slate-950 disabled:opacity-40">Ask</button>
        </form>
      </div>
    </Panel>
  )
}
