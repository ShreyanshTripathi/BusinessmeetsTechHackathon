import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import type { Assignment, Incident, WhatIfResult, Worker } from "@/types";
import { Btn } from "./bits";
import { X } from "lucide-react";

type Slot = { orig: Assignment; worker: string; worker_name: string; removed: boolean; check: WhatIfResult | null; checking: boolean };

export function ChangeSheet({ incident, open, onOpenChange }: { incident: Incident; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { act, showApplied } = useLive();
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSlots((incident.recommendation?.assignments ?? []).map((a) => ({ orig: a, worker: a.worker, worker_name: a.worker_name, removed: false, check: null, checking: false })));
    setReason("");
    api.workers().then((r) => setWorkers(r.workers)).catch(() => {});
  }, [open, incident]);

  const update = (i: number, patch: Partial<Slot>) => setSlots((s) => s.map((x, j) => (j === i ? { ...x, ...patch } : x)));

  const replace = async (i: number, wid: string) => {
    const w = workers.find((x) => x.id === wid);
    update(i, { worker: wid, worker_name: w?.name ?? wid, check: null, checking: true });
    const station = slots[i]?.orig.to_station ?? incident.stations[0];
    if (!station) { update(i, { checking: false }); return; }
    try { const r = await api.whatif(wid, station); update(i, { check: r, checking: false }); }
    catch { update(i, { checking: false }); }
  };

  const send = async () => {
    setBusy(true);
    const assignments = slots.filter((s) => !s.removed).map((s) => ({
      worker: s.worker, to_station: s.orig.to_station, to_zone: s.orig.to_zone, kind: s.orig.kind, task: s.orig.task,
    }));
    const r = await act(() => api.decide(incident.id, { decision: "modify", reason: reason.trim(), assignments }));
    setBusy(false);
    if (r) { showApplied(`Changed: ${incident.title}`, r.applied); onOpenChange(false); }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="font-display text-2xl">Change recommendation</SheetTitle>
          <SheetDescription className="text-base">{incident.title}. Remove or replace people. Calls to other teams still go out.</SheetDescription>
        </SheetHeader>
        <div className="mt-4 space-y-3 px-4">
          {slots.length === 0 && <p className="text-muted-foreground">No people moves in this recommendation.</p>}
          {slots.map((s, i) => (
            <div key={i} className={`rounded-lg border border-border p-3 ${s.removed ? "opacity-50" : ""}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-display text-lg font-bold">{s.orig.task}</div>
                  <div className="text-sm text-muted-foreground">
                    {s.orig.to_station ?? (s.orig.to_zone ? `Zone ${s.orig.to_zone}` : "")} · {s.orig.kind}
                  </div>
                </div>
                <Btn variant="ghost" onClick={() => update(i, { removed: !s.removed })}>
                  {s.removed ? "Restore" : <><X className="h-4 w-4" /> Remove</>}
                </Btn>
              </div>
              {!s.removed && (
                <div className="mt-2 space-y-2">
                  <Select value={s.worker} onValueChange={(v) => replace(i, v)}>
                    <SelectTrigger className="min-h-11 text-base"><SelectValue placeholder={s.worker_name} /></SelectTrigger>
                    <SelectContent className="max-h-80">
                      {!workers.some((w) => w.id === s.worker) && <SelectItem value={s.worker}>{s.worker_name} ({s.worker})</SelectItem>}
                      {workers.map((w) => (
                        <SelectItem key={w.id} value={w.id}>{w.name} · {w.id} · {w.status}{w.busy_with ? " · busy" : ""}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {s.checking && <p className="text-sm text-muted-foreground">Checking fit…</p>}
                  {s.check && (
                    <div className="space-y-1 text-sm">
                      {s.check.warnings.map((w, k) => <p key={k} className="text-high">⚠ {w}</p>)}
                      {s.check.benefits.map((b, k) => <p key={k} className="text-foreground">✓ {b}</p>)}
                      {s.check.warnings.length === 0 && s.check.benefits.length === 0 && <p className="text-muted-foreground">No issues found.</p>}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why are you changing it? (required)" className="min-h-20 text-lg" />
          <div className="flex justify-end gap-2 pb-6">
            <Btn onClick={() => onOpenChange(false)}>Cancel</Btn>
            <Btn variant="primary" disabled={!reason.trim() || busy} onClick={send}>{busy ? "Sending…" : "Apply change"}</Btn>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
