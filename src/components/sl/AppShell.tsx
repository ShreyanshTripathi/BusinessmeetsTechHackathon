import { useState, type ReactNode } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import { Bot, CheckCircle2, Flame, Menu, Pause, Volume2, VolumeX, Wifi, WifiOff, X } from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { hhmm } from "@/lib/time";
import { cn } from "@/lib/utils";
import { ActBtn, Btn, Code } from "./bits";
import { Copilot } from "./Copilot";

const NAV = [
  { to: "/", label: "Decide" },
  { to: "/line", label: "Line" },
  { to: "/people", label: "People" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const { snap, conn, demo, demoScenario, setDemoScenario, applied, clearApplied, voiceOn, setVoiceOn, voiceAsked, act } = useLive();
  const [copilot, setCopilot] = useState(false);
  const loc = useLocation();
  const crit = snap?.notifications.filter((n) => n.level === "critical" && !n.acknowledged) ?? [];
  const em = snap?.emergency;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
          <Link to="/" className="font-display text-2xl font-bold tracking-wide">ShiftLoop</Link>
          <div className="flex items-baseline gap-2">
            <span className="font-display text-4xl font-bold leading-none tabular-nums">{hhmm(snap?.clock)}</span>
            <span className="text-xs uppercase text-muted-foreground">plant time</span>
          </div>
          {snap && !snap.sim.running && (
            <span className="inline-flex items-center gap-1 rounded bg-secondary px-2 py-1 font-display text-base font-bold uppercase"><Pause className="h-4 w-4" /> Paused</span>
          )}
          <nav className="order-last flex w-full gap-1 sm:order-none sm:ml-4 sm:w-auto">
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} activeOptions={{ exact: true }}
                className="flex min-h-11 flex-1 items-center justify-center rounded-md px-5 font-display text-xl font-semibold text-muted-foreground hover:bg-accent sm:flex-none"
                activeProps={{ className: "bg-secondary !text-foreground" }}>
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <ConnBadge />
            {demo && (
              <div className="inline-flex rounded-md border border-input text-sm">
                {(["start", "emergency"] as const).map((s) => (
                  <button key={s} onClick={() => setDemoScenario(s)} className={cn("min-h-11 px-3 capitalize", demoScenario === s && "bg-secondary")}>{s}</button>
                ))}
              </div>
            )}
            <Btn variant="ghost" aria-label={voiceOn ? "Mute voice alerts" : "Turn on voice alerts"} onClick={() => setVoiceOn(!voiceOn)} className="px-3">
              {voiceOn ? <Volume2 className="h-5 w-5" /> : <VolumeX className="h-5 w-5 text-muted-foreground" />}
            </Btn>
            <Btn variant="outline" onClick={() => setCopilot(true)}><Bot className="h-5 w-5" /> Copilot</Btn>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button aria-label="Menu" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md hover:bg-accent"><Menu className="h-6 w-6" /></button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                {[["/alerts", "Notifications & expert queue"], ["/handover", "Shift handover"], ["/oversight", "Decision record"], ["/settings", "Demo controls & backend"]].map(([to, l]) => (
                  <DropdownMenuItem key={to} asChild className="min-h-11 text-base"><Link to={to}>{l}</Link></DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        {demo && <div className="bg-medium px-4 py-1 text-center font-display text-base font-bold uppercase tracking-wider text-medium-foreground">DEMO DATA: backend not connected</div>}
        {em && loc.pathname !== "/" && (
          <Link to="/" className="flex min-h-12 items-center gap-3 bg-critical px-4 py-2 text-critical-foreground">
            <Flame className="h-6 w-6" />
            <span className="font-display text-2xl font-bold uppercase">Emergency zone {em.zone}</span>
            <span className="text-lg">{em.accounted}/{em.people.length} accounted · {em.minutes} min</span>
            <span className="ml-auto font-display text-lg underline">Open emergency view →</span>
          </Link>
        )}
        {crit.map((n) => (
          <div key={n.id} className="flex flex-wrap items-center gap-3 bg-critical/90 px-4 py-2 text-critical-foreground">
            <Code code={n.code} className="text-2xl" />
            <span className="font-display text-xl font-bold">{hhmm(n.time)}</span>
            <span className="text-lg font-semibold">{n.title}</span>
            <span className="hidden text-base opacity-90 md:inline">{n.body}</span>
            <ActBtn className="ml-auto border-critical-foreground" onClick={() => act(() => api.ackNotification(n.id))}>Acknowledge</ActBtn>
          </div>
        ))}
      </header>

      {!voiceAsked && (
        <div className="flex flex-wrap items-center gap-3 border-b border-border bg-card px-4 py-3">
          <Volume2 className="h-6 w-6" />
          <span className="text-lg">Hear critical alerts in your earphones?</span>
          <Btn variant="primary" onClick={() => setVoiceOn(true)}>Enable voice alerts</Btn>
          <Btn variant="ghost" onClick={() => setVoiceOn(false)}>Not now</Btn>
        </div>
      )}

      {applied && (
        <div className="mx-4 mt-4 flex items-start gap-3 rounded-lg border border-border bg-card p-4">
          <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0" />
          <div className="flex-1">
            <div className="font-display text-xl font-bold">{applied.title}</div>
            {applied.items.length ? (
              <ul className="mt-1 list-disc pl-5 text-base">{applied.items.map((a, i) => <li key={i}>{a}</li>)}</ul>
            ) : <p className="text-base text-muted-foreground">Recorded. No changes applied.</p>}
          </div>
          <button aria-label="Dismiss" onClick={clearApplied} className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md hover:bg-accent"><X className="h-5 w-5" /></button>
        </div>
      )}

      <main className="mx-auto max-w-[1600px] p-4">
        {snap ? children : (
          <div className="py-24 text-center text-2xl text-muted-foreground">{conn === "connecting" ? "Connecting to the line…" : "Waiting for data…"}</div>
        )}
      </main>

      <Sheet open={copilot} onOpenChange={setCopilot}>
        <SheetContent className="flex w-full flex-col p-0 sm:max-w-lg">
          <SheetTitle className="sr-only">Copilot</SheetTitle>
          <Copilot />
        </SheetContent>
      </Sheet>
    </div>
  );
}

function ConnBadge() {
  const { conn } = useLive();
  if (conn === "live") return <span className="inline-flex items-center gap-1 px-2 text-sm text-muted-foreground"><Wifi className="h-4 w-4" /> Live</span>;
  if (conn === "demo") return null;
  return <span className="inline-flex items-center gap-1 px-2 text-sm text-medium"><WifiOff className="h-4 w-4" /> {conn === "connecting" ? "Connecting" : "Reconnecting"}</span>;
}
