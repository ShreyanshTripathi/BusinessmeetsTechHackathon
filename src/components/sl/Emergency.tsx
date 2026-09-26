import { useState } from "react";
import { Flame, UserCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { hhmm } from "@/lib/time";
import type { EmergencyView } from "@/types";
import { ActBtn, Btn } from "./bits";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

export function EmergencyPanel({ em }: { em: EmergencyView }) {
  const { act, setRestartPlan } = useLive();
  const [confirm, setConfirm] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const missing = em.people.filter((p) => !p.accounted);
  const ok = em.people.filter((p) => p.accounted);

  return (
    <div className="space-y-5">
      <div className="rounded-lg bg-critical p-5 text-critical-foreground">
        <div className="flex flex-wrap items-center gap-4">
          <Flame className="h-12 w-12" />
          <div>
            <div className="font-display text-5xl font-bold uppercase leading-none">Emergency · Zone {em.zone}</div>
            <div className="mt-1 text-xl">{em.reason}</div>
          </div>
          <div className="ml-auto text-right">
            <div className="font-display text-6xl font-bold leading-none">{em.minutes} min</div>
            <div className="text-lg">since {hhmm(em.started)}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <div className="flex items-baseline justify-between">
            <h2 className="font-display text-3xl font-bold">People accounted</h2>
            <span className={`font-display text-6xl font-bold ${missing.length ? "text-critical" : ""}`}>{em.accounted} / {em.people.length}</span>
          </div>
          {missing.length > 0 ? (
            <>
              <p className="text-lg text-muted-foreground">Tap a person when they are confirmed at the assembly point.</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {missing.map((p) => (
                  <ActBtn
                    key={p.id}
                    className="min-h-20 justify-start border-2 border-critical text-left"
                    disabled={pending === p.id}
                    onClick={async () => { setPending(p.id); await act(() => api.checkin(p.id)); setPending(null); }}
                  >
                    <div className="flex w-full items-center gap-3">
                      <div className="flex-1">
                        <div className="text-2xl font-bold">{p.name}</div>
                        <div className="font-sans text-base font-normal text-muted-foreground">{p.id}{p.station ? ` · ${p.station}` : ""}{p.fire_warden ? " · fire warden" : ""}</div>
                      </div>
                      <span className="text-base text-critical">{pending === p.id ? "…" : "NOT ACCOUNTED"}</span>
                    </div>
                  </ActBtn>
                ))}
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-border p-4 text-xl">Everyone is accounted for.</div>
          )}
          {ok.length > 0 && (
            <div>
              <div className="mb-2 text-sm uppercase tracking-wider text-muted-foreground">Accounted ({ok.length})</div>
              <div className="flex flex-wrap gap-2">
                {ok.map((p) => (
                  <span key={p.id} className="inline-flex items-center gap-1 rounded-md bg-secondary px-3 py-2 text-base">
                    <UserCheck className="h-4 w-4" /> {p.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
        <aside className="space-y-4 rounded-lg border border-border bg-card p-5">
          <Info label="Fire wardens" value={em.wardens.length ? em.wardens.join(", ") : "None in zone"} alert={!em.wardens.length} />
          <Info label="Exits" value={em.exits.join(" · ")} big />
          <Info label="Assembly point" value={em.assembly_point} big />
          <ActBtn variant="primary" big className="w-full" onClick={() => setConfirm(true)}>All clear</ActBtn>
        </aside>
      </div>

      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display text-2xl">Declare all clear for zone {em.zone}?</AlertDialogTitle>
            <AlertDialogDescription className="text-base">
              {missing.length > 0 ? `${missing.length} people are still not accounted for. ` : ""}This ends the emergency and returns a restart plan.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="min-h-11">Cancel</AlertDialogCancel>
            <AlertDialogAction className="min-h-11" onClick={async () => {
              const r = await act(() => api.allClear());
              if (r) setRestartPlan(r);
            }}>Yes, all clear</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function Info({ label, value, big, alert }: { label: string; value: string; big?: boolean; alert?: boolean }) {
  return (
    <div>
      <div className="text-sm uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`${big ? "font-display text-3xl font-bold" : "text-xl"} ${alert ? "text-critical" : ""}`}>{value}</div>
    </div>
  );
}

export function RestartPlanCard() {
  const { restartPlan, setRestartPlan } = useLive();
  if (!restartPlan) return null;
  return (
    <div className="rounded-lg border-2 border-foreground bg-card p-5">
      <div className="flex flex-wrap items-baseline gap-4">
        <h2 className="font-display text-3xl font-bold">Restart plan · Zone {restartPlan.zone}</h2>
        <span className="font-display text-2xl">{restartPlan.duration_min} min</span>
        <span className="font-display text-2xl">{restartPlan.cars_to_recover} cars to recover</span>
        <Btn className="ml-auto" onClick={() => setRestartPlan(null)}>Dismiss</Btn>
      </div>
      <ol className="mt-3 list-decimal space-y-1 pl-6 text-lg">
        {restartPlan.steps.map((s, i) => <li key={i}>{s}</li>)}
      </ol>
    </div>
  );
}
