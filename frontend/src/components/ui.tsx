import type { ReactNode } from 'react'
import { TONE_BADGE, type Tone } from '../format'

export function Badge({ tone = 'slate', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium tracking-wide ${TONE_BADGE[tone]}`}>
      {children}
    </span>
  )
}

export function Panel({ title, action, children, className = '' }: { title: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`flex min-h-0 flex-col rounded-xl border border-slate-800 bg-slate-900/60 ${className}`}>
      <header className="flex items-center justify-between gap-2 border-b border-slate-800 px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">{title}</h2>
        {action}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </section>
  )
}

export function Button({
  children, onClick, tone = 'default', disabled, type = 'button', label, title,
}: {
  children: ReactNode
  onClick?: () => void
  tone?: 'primary' | 'danger' | 'default' | 'ghost'
  disabled?: boolean
  type?: 'button' | 'submit'
  label?: string
  title?: string
}) {
  const styles = {
    primary: 'bg-emerald-500 text-slate-950 hover:bg-emerald-400',
    danger: 'bg-red-500 text-white hover:bg-red-400',
    default: 'bg-slate-800 text-slate-100 hover:bg-slate-700 ring-1 ring-slate-700',
    ghost: 'text-slate-300 hover:bg-slate-800',
  }[tone]
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={title}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${styles}`}
    >
      {children}
    </button>
  )
}
