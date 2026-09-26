import { createFileRoute } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { ChevronDown, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { hhmm, minutesBetween } from "@/lib/time";
import { ActBtn, Btn, Code, sevBorder } from "@/components/sl/bits";
import { DecisionCard } from "@/components/sl/DecisionCard";
import { ProposalCard } from "@/components/sl/ProposalCard";
import { EmergencyPanel, RestartPlanCard } from "@/components/sl/Emergency";
import { cn } from "@/lib/utils";
import type { Snapshot } from "@/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Decide · ShiftLoop Supervisor" },
      { name: "description", content: "Decisions waiting for the line supervisor: safety first, AI recommends, human decides." },
      { property: "og:title", content: "Decide · ShiftLoop Supervisor" },
      { property: "og:description", content: "Live decision support for a car assembly line supervisor." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: DecidePage,
});

function DecidePage() {
  const { snap } = useLive();
  if (!snap) return null;
  if (snap.emergency) return <EmergencyPanel em={snap.emergency} />;
  const [first, ...other] = snap.incidents.active;
  return (
    <div className="mx-auto max-w-7xl">
      <RestartPlanCard />
      <SafetyNotice snap={snap} />
      <div className="grid items-start gap-0 lg:grid-cols-[minmax(0,1fr)_minmax(300px,320px)] xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 py-7 lg:pr-10 lg:py-10">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-2">
            <div>
              <p className="text-sm font-bold uppercase text-muted-foreground">Supervisor decision</p>
              <h1 className="mt-1 font-display text-3xl leading-tight sm:text-4xl">Needs your decision</h1>
            </div>
            <span className="text-sm text-muted-foreground">{snap.attention.signals.toLocaleString("en-US")} signals filtered → {snap.attention.active} decision{snap.attention.active === 1 ? "" : "s"}</span>
          </div>
          {first ? <DecisionCard inc={first} clock={snap.clock} notifications={snap.notifications} featured /> : (
            <div className="border-t border-border py-12 text-2xl font-semibold">Nothing needs you right now.</div>
          )}
          {other.length > 0 && <Collapsible label={`${other.length} more decision${other.length === 1 ? "" : "s"}`}>
            <div className="space-y-4">{other.map((inc) => <DecisionCard key={inc.id} inc={inc} clock={snap.clock} notifications={snap.notifications} />)}</div>
          </Collapsible>}
          {snap.incidents.held.length > 0 && <Collapsible label={`${snap.incidents.held.length} held back`}>
            <div className="space-y-4">{snap.incidents.held.map((inc) => <DecisionCard key={inc.id} inc={inc} clock={snap.clock} notifications={snap.notifications} />)}</div>
          </Collapsible>}
          {(snap.proposals.length > 0 || snap.incidents.in_progress.length > 0) && <Collapsible label={`More shift activity · ${snap.proposals.length + snap.incidents.in_progress.length}`}>
            {snap.proposals.length > 0 && <section className="mb-8"><h2 className="mb-3 text-xl font-semibold">Copilot proposals</h2><div className="grid gap-3 sm:grid-cols-2">{snap.proposals.map((p) => <ProposalCard key={p.id} p={p} />)}</div></section>}
            {snap.incidents.in_progress.length > 0 && <section><h2 className="mb-3 text-xl font-semibold">In progress</h2><div className="space-y-2">{snap.incidents.in_progress.map((i) => <div key={i.id} className={cn("border-l-4 bg-card p-4", sevBorder(i.severity))}><strong>Zone {i.zone} · {i.stations.join(" ")}</strong><span className="ml-3 text-muted-foreground">{hhmm(i.updated)}</span><div>{i.title}</div></div>)}</div></section>}
          </Collapsible>}
        </div>
        <aside className="min-w-0 border-t border-border bg-secondary/40 px-5 py-7 lg:min-h-[calc(100vh-132px)] lg:border-t-0 lg:border-l lg:px-7 lg:py-10">
          <Escalations snap={snap} />
          <LineStatus snap={snap} />
        </aside>
      </div>
    </div>
  );
}

function SafetyNotice({ snap }: { snap: Snapshot }) {
  if (!snap.kpis.open_safety) return null;
  return <div className="flex items-center gap-3 border-b-2 border-foreground bg-secondary px-5 py-4"><ShieldAlert className="h-7 w-7 shrink-0" /><strong className="text-xl">{snap.kpis.open_safety} open safety issue{snap.kpis.open_safety === 1 ? "" : "s"}</strong></div>;
}

function Collapsible({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <section className="mt-6 border-t border-border pt-3">
    <Btn variant="ghost" aria-expanded={open} onClick={() => setOpen(!open)} className="w-full justify-between px-1 text-left text-base font-semibold">{label}<ChevronDown className={cn("h-5 w-5 transition-transform", open && "rotate-180")} /></Btn>
    {open && <div className="mt-4">{children}</div>}
  </section>;
}

function Escalations({ snap }: { snap: Snapshot }) {
  const { act } = useLive();
  const waiting = snap.escalations.filter((e) => !e.acknowledged_at);
  const done = snap.escalations.filter((e) => e.acknowledged_at && minutesBetween(e.acknowledged_at, snap.clock) <= 30);
  return <section>
    <div className="mb-4 flex items-baseline justify-between gap-3"><h2 className="text-lg font-bold">Waiting on confirmation</h2><span className="text-xl font-bold tabular-nums">{waiting.length}</span></div>
    {waiting.length === 0 ? <p className="border-t border-border py-4 text-muted-foreground">No teams waiting to confirm.</p> : <div className="space-y-3">{waiting.map((e) => {
      const code = snap.notifications.find((n) => n.incident_id === e.incident_id && n.code)?.code;
      return <div key={e.id} className="border-t-2 border-foreground bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-xl capitalize">{e.team}</strong><span className="font-bold">{minutesBetween(e.time, snap.clock)} min waiting</span></div>
        {code && <Code code={code} className="text-sm" />}
        <p className="mt-1 leading-snug">{e.message}</p>
        <p className="mt-1 text-sm text-muted-foreground">Called {hhmm(e.time)}{e.reminders ? ` · ${e.reminders} reminder${e.reminders > 1 ? "s" : ""}` : ""}</p>
        <ActBtn className="mt-3 w-full" onClick={() => act(() => api.ackEscalation(e.id))}>Confirmed</ActBtn>
      </div>;
    })}</div>}
    {done.length > 0 && <Collapsible label={`${done.length} recently confirmed`}><div className="space-y-2 text-sm">{done.map((e) => <p key={e.id}><span className="capitalize">{e.team}</span> · {hhmm(e.acknowledged_at)} · {e.message}</p>)}</div></Collapsible>}
  </section>;
}

function LineStatus({ snap }: { snap: Snapshot }) {
  const k = snap.kpis;
  const top = Object.entries(k.downtime_min).slice(0, 3);
  const impact = Object.entries(k.impact);
  return <section className="mt-10 border-t border-border pt-7">
    <h2 className="mb-5 text-lg font-bold">Line vs plan</h2>
    <div className="grid grid-cols-2 gap-x-4 gap-y-5">
      <Stat label="Cars / plan" value={`${k.cars_built} / ${k.plan}`} />
      <Stat label="Output" value={`${k.output_pct}%`} />
      <Stat label="Downtime" value={`${k.downtime_total_min} min`} />
      <Stat label="Defects" value={String(k.defects)} />
    </div>
    <div className="mt-6 space-y-2 border-t border-border pt-4 text-sm">
      <div className="flex justify-between"><span>Open incidents</span><strong>{k.open_incidents}</strong></div>
      {k.open_safety > 0 && <div className="flex justify-between font-semibold"><span>Open safety issues</span><strong>{k.open_safety}</strong></div>}
      {top.length > 0 && <p className="text-muted-foreground">Most downtime: {top.map(([s, m]) => `${s} ${m} min`).join(" · ")}</p>}
    </div>
    {impact.length > 0 && <Collapsible label="Saved by decisions this shift"><div className="space-y-2 text-sm">{impact.map(([key, value]) => <p key={key}>{key.replaceAll("_", " ")}: <strong>{value}</strong></p>)}</div></Collapsible>}
  </section>;
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div><div className="text-sm text-muted-foreground">{label}</div><div className="text-2xl font-bold tabular-nums">{value}</div></div>;
}
