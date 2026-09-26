import { useState } from "react";
import { ChevronDown, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { hhmm, minutesBetween } from "@/lib/time";
import { cn } from "@/lib/utils";
import type { Incident, Notification } from "@/types";
import { ACTION_LABEL, ActBtn, agentLabel, Code, HARD_RULE_LABEL, SevBadge, sevBorder } from "./bits";
import { ReasonDialog } from "./ReasonDialog";
import { ChangeSheet } from "./ChangeSheet";

export function DecisionCard({ inc, clock, notifications, compact }: { inc: Incident; clock: string; notifications: Notification[]; compact?: boolean }) {
  const { act, showApplied } = useLive();
  const [open, setOpen] = useState(false);
  const [dismissOpen, setDismissOpen] = useState(false);
  const [changeOpen, setChangeOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const rec = inc.recommendation;
  const code = notifications.find((n) => n.incident_id === inc.id && n.code)?.code ?? null;
  const unsure = inc.confidence < 0.6;
  const where = rec ? (rec.scope === "zone" ? `Zone ${rec.target}` : rec.scope === "station" ? rec.target : "Section") : null;

  const accept = async () => {
    setBusy(true);
    const r = await act(() => api.decide(inc.id, { decision: "accept", reason: "" }));
    setBusy(false);
    if (r) showApplied(`Accepted: ${inc.title}`, r.applied);
  };

  return (
    <article className={cn("rounded-lg border border-border border-l-8 bg-card p-4 sm:p-5", sevBorder(inc.severity))}>
      <header className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-5xl font-bold leading-none">{inc.zone}</span>
          <span className="font-display text-3xl font-bold leading-none">{inc.stations.join(" · ")}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SevBadge s={inc.severity} />
          <Code code={code} />
          {rec?.hard_rule && (
            <span className="inline-flex items-center gap-1 rounded border border-foreground px-2 py-0.5 font-display text-sm font-bold uppercase">
              <ShieldAlert className="h-4 w-4" /> {HARD_RULE_LABEL[rec.hard_rule] ?? rec.hard_rule} · non-negotiable
            </span>
          )}
        </div>
        <div className="ml-auto text-right text-sm text-muted-foreground">
          <div>opened {hhmm(inc.opened)} · {minutesBetween(inc.opened, clock)} min ago</div>
          <div className={cn("font-display text-lg", unsure && "text-medium")}>
            {Math.round(inc.confidence * 100)}% confident{unsure && " · unsure"}
          </div>
        </div>
      </header>

      <h3 className="mt-3 text-2xl font-semibold leading-snug">{inc.title}</h3>
      {inc.likely_cause && <p className="mt-1 text-lg text-muted-foreground">Likely cause: {inc.likely_cause}</p>}

      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
        {inc.agents.map((a) => <span key={a} className="rounded-full bg-secondary px-3 py-1">{agentLabel(a)}</span>)}
        {inc.agents.length > 1 && <span className="font-semibold text-foreground">Cross-function finding</span>}
      </div>

      {rec ? (
        <div className="mt-4 rounded-md bg-secondary/60 p-4">
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="text-sm uppercase tracking-wider text-muted-foreground">AI recommends</span>
            <span className={cn("font-display text-3xl font-bold", rec.action === "emergency" && "text-critical")}>
              {ACTION_LABEL[rec.action] ?? rec.action}
            </span>
            {where && <span className="font-display text-3xl font-bold">{where}</span>}
          </div>
          <p className="mt-1 text-lg">{rec.summary}</p>
          {!compact && rec.steps.length > 0 && (
            <ol className="mt-2 list-decimal space-y-0.5 pl-6 text-base">
              {(open ? rec.steps : rec.steps.slice(0, 2)).map((s, i) => <li key={i}>{s}</li>)}
            </ol>
          )}
          {rec.assignments.length > 0 && (
            <div className="mt-3">
              <div className="text-sm uppercase tracking-wider text-muted-foreground">Sending</div>
              <ul className="mt-1 space-y-1">
                {rec.assignments.map((a, i) => (
                  <li key={i} className="text-lg">
                    <span className="font-semibold">{a.worker_name}</span>
                    <span className="text-muted-foreground"> → </span>
                    <span className="font-display font-bold">{a.to_station ?? (a.to_zone ? `Zone ${a.to_zone}` : "")}</span>
                    <span className="text-muted-foreground"> · {a.task}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {rec.escalations.length > 0 && (
            <p className="mt-2 text-lg"><span className="text-muted-foreground">Will call: </span><span className="font-semibold">{rec.escalations.join(", ")}</span></p>
          )}
        </div>
      ) : (
        <p className="mt-3 text-muted-foreground">No recommendation yet.</p>
      )}

      <button onClick={() => setOpen(!open)} className="mt-3 inline-flex min-h-11 items-center gap-1 text-base text-muted-foreground hover:text-foreground">
        <ChevronDown className={cn("h-5 w-5 transition-transform", open && "rotate-180")} />
        {open ? "Hide details" : `Details · ${inc.evidence.length} evidence${rec && rec.steps.length > 2 ? ` · all ${rec.steps.length} steps` : ""}`}
      </button>
      {open && (
        <ul className="mt-1 space-y-1 border-l-2 border-border pl-4 text-base text-muted-foreground">
          {inc.evidence.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      )}

      {!compact && inc.status === "open" && (
        <div className="mt-4 flex flex-wrap gap-2">
          <ActBtn variant="primary" big onClick={accept} disabled={busy}>{busy ? "Sending…" : "Accept"}</ActBtn>
          <ActBtn big onClick={() => setChangeOpen(true)}>Change</ActBtn>
          <ActBtn big variant="ghost" onClick={() => setDismissOpen(true)}>Dismiss</ActBtn>
        </div>
      )}

      <ReasonDialog
        open={dismissOpen} onOpenChange={setDismissOpen} title="Dismiss recommendation" description={inc.title} confirmLabel="Dismiss"
        onConfirm={async (reason) => {
          const r = await act(() => api.decide(inc.id, { decision: "dismiss", reason }));
          if (r) { showApplied(`Dismissed: ${inc.title}`, r.applied); setDismissOpen(false); }
        }}
      />
      {changeOpen && <ChangeSheet incident={inc} open={changeOpen} onOpenChange={setChangeOpen} />}
    </article>
  );
}
