import { createFileRoute } from "@tanstack/react-router";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { hhmm } from "@/lib/time";
import { cn } from "@/lib/utils";
import { ActBtn, Code, Empty, Section, sevBorder } from "@/components/sl/bits";

export const Route = createFileRoute("/alerts")({
  head: () => ({
    meta: [
      { title: "Notifications · ShiftLoop Supervisor" },
      { name: "description", content: "All shift notifications with acknowledge, plus low-confidence detections sent to a quality expert." },
      { property: "og:title", content: "Notifications · ShiftLoop Supervisor" },
      { property: "og:description", content: "Shift notification log and expert queue." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: AlertsPage,
});

function AlertsPage() {
  const { snap, act } = useLive();
  if (!snap) return null;
  return (
    <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
      <Section title="Notifications">
        {snap.notifications.length === 0 ? <Empty>No notifications this shift.</Empty> : (
          <div className="space-y-2">
            {snap.notifications.map((n) => (
              <div key={n.id} className={cn("flex flex-wrap items-start gap-3 rounded-lg border border-border border-l-8 bg-card p-3", sevBorder(n.level === "info" ? null : n.level), n.acknowledged && "opacity-60")}>
                <span className="font-display text-xl font-bold">{hhmm(n.time)}</span>
                <Code code={n.code} />
                <div className="min-w-0 flex-1">
                  <div className="text-lg font-semibold">{n.title}</div>
                  <div className="text-base text-muted-foreground">{n.body}{n.incident_id ? ` · ${n.incident_id}` : ""}</div>
                </div>
                {n.acknowledged ? <span className="text-sm text-muted-foreground">acknowledged</span> : (
                  <ActBtn onClick={() => act(() => api.ackNotification(n.id))}>Acknowledge</ActBtn>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>
      <Section title={`Expert queue · ${snap.expert_queue.length}`}>
        {snap.expert_queue.length === 0 ? <Empty>No detections waiting for an expert.</Empty> : (
          <div className="space-y-2">
            {snap.expert_queue.map((q) => (
              <div key={q.id} className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-baseline gap-2"><span className="font-display text-2xl font-bold">{q.station}</span><span className="text-muted-foreground">{hhmm(q.time)}</span><span className="ml-auto">{Math.round(q.confidence * 100)}%</span></div>
                <ul className="text-base text-muted-foreground">{q.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}
