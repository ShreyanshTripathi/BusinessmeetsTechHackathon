import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ChevronDown, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { hhmm, minutesBetween } from "@/lib/time";
import { ActBtn, Code, Empty, Section, sevBorder } from "@/components/sl/bits";
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
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(340px,1fr)]">
      <div className="space-y-6">
        <RestartPlanCard />
        <DangerStrip snap={snap} />
        <Section title="Needs your decision" right={<span className="font-display text-lg text-muted-foreground">{snap.attention.signals.toLocaleString("en-US")} signals filtered → {snap.attention.active} decision{snap.attention.active === 1 ? "" : "s"}</span>}>
          {snap.incidents.active.length === 0 ? (
            <Empty>Nothing needs you right now.</Empty>
          ) : (
            <div className="space-y-4">
              {snap.incidents.active.map((inc) => <DecisionCard key={inc.id} inc={inc} clock={snap.clock} notifications={snap.notifications} />)}
            </div>
          )}
          <Collapsible label={`${snap.incidents.held.length} more held back`} show={snap.incidents.held.length > 0}>
            {snap.incidents.held.map((inc) => <DecisionCard key={inc.id} inc={inc} clock={snap.clock} notifications={snap.notifications} />)}
          </Collapsible>
        </Section>
        {snap.proposals.length > 0 && (
          <Section title="Copilot proposals">
            <div className="grid gap-3 md:grid-cols-2">{snap.proposals.map((p) => <ProposalCard key={p.id} p={p} />)}</div>
          </Section>
        )}
      </div>
      <div className="space-y-6">
        <Escalations snap={snap} />
        <Section title="In progress">
          {snap.incidents.in_progress.length === 0 ? <Empty>No accepted work in progress.</Empty> : (
            <div className="space-y-2">
              {snap.incidents.in_progress.map((i) => (
                <div key={i.id} className={cn("rounded-lg border border-border border-l-4 bg-card p-3", sevBorder(i.severity))}>
                  <div className="flex items-baseline gap-2"><span className="font-display text-2xl font-bold">{i.zone} · {i.stations.join(" ")}</span><span className="ml-auto text-sm text-muted-foreground">{hhmm(i.updated)}</span></div>
                  <div className="text-lg">{i.title}</div>
                </div>
              ))}
            </div>
          )}
        </Section>
        <KpiPanel snap={snap} />
      </div>
    </div>
  );
}

function DangerStrip({ snap }: { snap: Snapshot }) {
  const safety = snap.kpis.open_safety;
  return (
    <div className={cn("flex items-center gap-4 rounded-lg border p-4", safety ? "border-critical bg-critical/10" : "border-border bg-card")}>
      <ShieldCheck className={cn("h-10 w-10", safety ? "text-critical" : "text-muted-foreground")} />
      <div className="font-display text-3xl font-bold">
        {safety ? `${safety} open safety issue${safety > 1 ? "s" : ""}` : "No one in danger right now"}
      </div>
    </div>
  );
}

function Collapsible({ label, show, children }: { label: string; show: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  if (!show) return null;
  return (
    <div>
      <button onClick={() => setOpen(!open)} className="inline-flex min-h-11 items-center gap-2 text-lg text-muted-foreground hover:text-foreground">
        <ChevronDown className={cn("h-5 w-5 transition-transform", open && "rotate-180")} /> {label}
      </button>
      {open && <div className="mt-2 space-y-4 opacity-90">{children}</div>}
    </div>
  );
}

function Escalations({ snap }: { snap: Snapshot }) {
  const { act } = useLive();
  const waiting = snap.escalations.filter((e) => !e.acknowledged_at);
  const done = snap.escalations.filter((e) => e.acknowledged_at);
  return (
    <Section title="Waiting on confirmation">
      {waiting.length === 0 ? <Empty>Every team you called has confirmed.</Empty> : (
        <div className="space-y-2">
          {waiting.map((e) => {
            const code = snap.notifications.find((n) => n.incident_id === e.incident_id && n.code)?.code;
            return (
              <div key={e.id} className="rounded-lg border-2 border-high bg-card p-4">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="font-display text-2xl font-bold capitalize">{e.team}</span>
                  {code && <Code code={code} className="text-base" />}
                  <span className="ml-auto font-display text-2xl font-bold text-high">waiting {minutesBetween(e.time, snap.clock)} min</span>
                </div>
                <div className="text-lg">{e.message}</div>
                <div className="text-sm text-muted-foreground">called {hhmm(e.time)}{e.reminders ? ` · ${e.reminders} reminder${e.reminders > 1 ? "s" : ""} sent` : ""}</div>
                <ActBtn className="mt-2 w-full" onClick={() => act(() => api.ackEscalation(e.id))}>Confirmed</ActBtn>
              </div>
            );
          })}
        </div>
      )}
      {done.length > 0 && (
        <div className="space-y-1 text-base text-muted-foreground">
          {done.map((e) => <div key={e.id}>✓ <span className="capitalize">{e.team}</span> confirmed at {hhmm(e.acknowledged_at)}: {e.message}</div>)}
        </div>
      )}
    </Section>
  );
}

const IMPACT_LABEL: Record<string, [string, string]> = {
  downtime_avoided_min: ["Downtime avoided", "min"],
  energy_saved_kwh: ["Energy saved", "kWh"],
  rework_avoided_cars: ["Rework avoided", "cars"],
};

function KpiPanel({ snap }: { snap: Snapshot }) {
  const k = snap.kpis;
  const top = Object.entries(k.downtime_min).slice(0, 3);
  const impact = Object.entries(k.impact);
  return (
    <Section title="Line vs plan">
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="grid grid-cols-3 gap-3">
          <Stat label="Cars / plan" value={`${k.cars_built} / ${k.plan}`} />
          <Stat label="Output" value={`${k.output_pct}%`} />
          <Stat label="Downtime" value={`${k.downtime_total_min} min`} />
          <Stat label="Defects" value={String(k.defects)} />
          <Stat label="Open incidents" value={String(k.open_incidents)} />
          <Stat label="Open safety" value={String(k.open_safety)} alert={k.open_safety > 0} />
        </div>
        {top.length > 0 && (
          <div className="mt-3 text-base"><span className="text-muted-foreground">Most downtime: </span>{top.map(([s, m]) => `${s} ${m} min`).join(" · ")}</div>
        )}
        {impact.length > 0 && (
          <div className="mt-3 border-t border-border pt-3">
            <div className="text-sm uppercase tracking-wider text-muted-foreground">Saved by decisions this shift</div>
            <div className="mt-1 flex flex-wrap gap-4">
              {impact.map(([key, v]) => (
                <div key={key}><span className="font-display text-2xl font-bold">{v} {IMPACT_LABEL[key]?.[1] ?? ""}</span> <span className="text-muted-foreground">{IMPACT_LABEL[key]?.[0] ?? key}</span></div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Section>
  );
}

function Stat({ label, value, alert }: { label: string; value: string; alert?: boolean }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("font-display text-2xl font-bold tabular-nums", alert && "text-critical")}>{value}</div>
    </div>
  );
}
