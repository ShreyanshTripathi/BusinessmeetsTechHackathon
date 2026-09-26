import { useState } from 'react'
import type { Language } from '../types'
import { Button, Panel } from './ui'

export default function HandoverView({ onGenerate }: { onGenerate: (language: Language) => Promise<{ text: string; mode: string }> }) {
  const [language, setLanguage] = useState<Language>('en')
  const [text, setText] = useState('')
  const [mode, setMode] = useState('')
  const [busy, setBusy] = useState(false)

  const generate = async () => {
    setBusy(true)
    try {
      const res = await onGenerate(language)
      setText(res.text)
      setMode(res.mode)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel
      title="Shift handover"
      className="h-full"
      action={
        <div className="flex items-center gap-2">
          <select aria-label="Language" value={language} onChange={(e) => setLanguage(e.target.value as Language)}
            className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-200 ring-1 ring-slate-700">
            <option value="en">English</option>
            <option value="de">Deutsch</option>
            <option value="pl">Polski</option>
          </select>
          <Button tone="primary" onClick={generate} disabled={busy}>{busy ? 'Writing…' : 'Generate'}</Button>
        </div>
      }
    >
      <div className="flex h-full flex-col gap-2 p-4">
        <p className="text-xs text-slate-400">
          Drafted from the shift's events and decisions. Edit before sending; supervisor corrections are listed separately
          so engineering can review them.{mode && ` (${mode === 'claude' ? 'written by Claude' : 'offline template'})`}
        </p>
        <textarea value={text} onChange={(e) => setText(e.target.value)} aria-label="Handover text"
          className="min-h-[420px] flex-1 rounded-md bg-slate-950 p-3 font-mono text-[13px] leading-relaxed text-slate-100 ring-1 ring-slate-700 focus:outline-none focus:ring-sky-500" />
      </div>
    </Panel>
  )
}
