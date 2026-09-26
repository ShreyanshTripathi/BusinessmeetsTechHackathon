import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { hhmm } from "@/lib/time";
import { agentLabel, Empty, Section } from "@/components/sl/bits";
import type { Oversight } from "@/types";

export const Route = createFileRoute("/oversight")({
  head: () => ({
    meta: [
      { title: "Decision record · ShiftLoop Supervisor" },
      { name: "description", content: "Every AI recommendation and the human decision made on it, with data use for the works council." },
      { property: "og:title", content: "Decision record · ShiftLoop Supervisor" },
      { property: "og:description", content: "Human oversight record for auditors and the works council." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: OversightPage,
});

function OversightPage() {
  const { snap, demo } = useLive();
  const [o, setO] = useState<Oversight | null>(null);
  useEffect(() => {
    if (demo) return;
    api.oversight().then(setO).catch(() => {});
  }, [snap?.attention.incidents, snap?.clock, demo]);

  if (demo) return <Empty>Connect a backend to see the decision record.</Empty>;
  if (!o) return <Empty>Loading decision record…</Empty>;
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <Big label="Decisions" v={o.decisions.total} />
        <Big label="Accepted" v={o.decisions.accept} />
        <Big label="Changed" v={o.decisions.modify} />
        <Big label="Dismissed" v={o.decisions.dismiss} />
        <Big label="Override rate" v={`${Math.round(o.override_rate * 100)}%`} />
        <Big label="Decided by a human" v={`${o.human_decided_pct}%`} />
      </div>
      <p className="text-lg text-muted-foreground">Every decision made by a human. The AI only recommends. {o.expert_queue} detections sent to a quality expert.</p>

      <Section title="Per agent">
        <div className="grid gap-3 md:grid-cols-3">
          {Object.entries(o.agents).map(([k, a]) => (
            <div key={k} className="rounded-lg border border-border bg-card p-4">
              <div className="font-display text-2xl font-bold">{agentLabel(k)}</div>
              <div className="mt-1 grid grid-cols-5 gap-1 text-center text-sm">
                {(["events", "incidents", "decisions", "accepted", "overridden"] as const).map((f) => (
                  <div key={f}><div className="font-display text-xl font-bold">{a[f]}</div><div className="text-muted-foreground">{f}</div></div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Decision log">
        {o.log.length === 0 ? <Empty>No decisions yet this shift.</Empty> : (
          <div className="space-y-2">
            {o.log.map((d) => (
              <div key={d.id} className="rounded-lg border border-border bg-card p-3">
                <div className="flex flex-wrap items-baseline gap-3">
                  <span className="font-display text-xl font-bold">{hhmm(d.time)}</span>
                  <span className="rounded bg-secondary px-2 font-display text-lg font-bold uppercase">{d.decision === "modify" ? "changed" : d.decision}</span>
                  <span className="text-lg">{d.incident_title}</span>
                  <span className="ml-auto text-sm text-muted-foreground">by {d.decided_by} · {d.agents.map(agentLabel).join(", ")}</span>
                </div>
                <div className="text-base text-muted-foreground">Recommended: {d.recommended}{d.reason ? ` · Reason: ${d.reason}` : ""}</div>
                {d.applied.length > 0 && <ul className="mt-1 list-disc pl-5 text-sm">{d.applied.map((a, i) => <li key={i}>{a}</li>)}</ul>}
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Data use">
        <div className="grid gap-3 md:grid-cols-3">
          {Object.entries(o.data_use).map(([k, d]) => (
            <div key={k} className="rounded-lg border border-border bg-card p-4 text-base">
              <div className="font-display text-2xl font-bold">{agentLabel(k)}</div>
              <p className="mt-1">{d.purpose}</p>
              <div className="mt-2 text-sm text-muted-foreground">Uses</div>
              <ul className="list-disc pl-5">{d.uses.map((u, i) => <li key={i}>{u}</li>)}</ul>
              <div className="mt-2 text-sm text-muted-foreground">Never</div>
              <ul className="list-disc pl-5">{d.never.map((u, i) => <li key={i}>{u}</li>)}</ul>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Works council">
        <div className="grid gap-2 md:grid-cols-2">
          {Object.entries(o.works_council).map(([k, v]) => (
            <div key={k} className="flex justify-between rounded-md border border-border bg-card px-3 py-2 text-base">
              <span>{k.replace(/_/g, " ")}</span>
              <span className="font-semibold">{typeof v === "boolean" ? (v ? "Yes" : "No") : v}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

function Big({ label, v }: { label: string; v: number | string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-display text-4xl font-bold">{v}</div>
    </div>
  );
}
