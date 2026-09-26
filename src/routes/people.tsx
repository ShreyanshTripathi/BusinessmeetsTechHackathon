import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { Btn, Empty, Section } from "@/components/sl/bits";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { WhatIfResult, Worker } from "@/types";
import mockWorkers from "@/mocks/workers.json";

export const Route = createFileRoute("/people")({
  head: () => ({
    meta: [
      { title: "People · ShiftLoop Supervisor" },
      { name: "description", content: "Workers on shift, qualifications, hours and a what-if placement check." },
      { property: "og:title", content: "People · ShiftLoop Supervisor" },
      { property: "og:description", content: "Who is on shift and who could cover which station." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: PeoplePage,
});

type Stn = { id: string; zone: string; name: string; safety_critical: boolean };

function PeoplePage() {
  const { snap, demo } = useLive();
  const [workers, setWorkers] = useState<Worker[] | null>(null);
  const [stations, setStations] = useState<Stn[]>([]);
  const [zone, setZone] = useState("all");
  const [status, setStatus] = useState("all");
  const [role, setRole] = useState("all");

  useEffect(() => {
    if (demo) {
      setWorkers(mockWorkers.workers as unknown as Worker[]);
      setStations((snap?.stations ?? []).map((s) => ({ id: s.id, zone: s.zone, name: s.name, safety_critical: s.safety_critical })));
      return;
    }
    api.workers().then((r) => { setWorkers(r.workers); setStations(r.stations); }).catch(() => {});
  }, [snap?.clock, demo]);

  const list = useMemo(() => (workers ?? []).filter((w) =>
    (zone === "all" || w.zone === zone) && (status === "all" || w.status === status) && (role === "all" || w.role === role)), [workers, zone, status, role]);

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(340px,1fr)]">
      <Section title="On shift" right={workers && <span className="text-muted-foreground">{list.length} of {workers.length}</span>}>
        <div className="flex flex-wrap gap-2">
          <Filter value={zone} onChange={setZone} label="Zone" opts={["A", "B", "C", "D"]} />
          <Filter value={status} onChange={setStatus} label="Status" opts={["present", "break", "absent"]} />
          <Filter value={role} onChange={setRole} label="Role" opts={["operator", "floater", "maintenance", "team_lead"]} />
        </div>
        {!workers ? <Empty>Loading people…</Empty> : list.length === 0 ? <Empty>No one matches these filters.</Empty> : (
          <div className="grid gap-2 md:grid-cols-2">
            {list.map((w) => <WorkerCard key={w.id} w={w} />)}
          </div>
        )}
      </Section>
      <WhatIf workers={workers ?? []} stations={stations} disabled={demo} />
    </div>
  );
}

function Filter({ value, onChange, label, opts }: { value: string; onChange: (v: string) => void; label: string; opts: string[] }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="min-h-11 w-40 text-base"><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value="all">{label}: all</SelectItem>
        {opts.map((o) => <SelectItem key={o} value={o}>{label}: {o.replace("_", " ")}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

function WorkerCard({ w }: { w: Worker }) {
  const overHours = w.hours_worked >= 10;
  return (
    <div className={cn("rounded-lg border border-border bg-card p-3", w.status === "absent" && "opacity-55")}>
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-semibold">{w.name}</span>
        <span className="font-mono text-sm text-muted-foreground">{w.id}</span>
        <span className="ml-auto font-display text-2xl font-bold">{w.station ?? `Zone ${w.zone}`}</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-1 text-sm">
        <Tag>{w.role.replace("_", " ")}</Tag>
        <Tag>{w.status}</Tag>
        {w.fire_warden && <Tag strong>Fire warden</Tag>}
        {w.first_aider && <Tag strong>First aider</Tag>}
        {w.busy_with && <Tag strong>Busy · {w.busy_with}</Tag>}
        <span className={cn("ml-auto", overHours ? "font-bold text-high" : "text-muted-foreground")}>{w.hours_worked.toFixed(1)} / 10 h</span>
      </div>
      <div className="mt-2 text-sm text-muted-foreground">
        {Object.entries(w.qualifications).map(([s, l]) => (
          <span key={s} className="mr-2 inline-block">{s}:L{l}{w.qual_expiry[s] ? ` (exp ${w.qual_expiry[s]})` : ""}</span>
        ))}
      </div>
      {w.languages.length > 0 && <div className="text-xs uppercase text-muted-foreground">{w.languages.join(" · ")}</div>}
    </div>
  );
}
function Tag({ children, strong }: { children: React.ReactNode; strong?: boolean }) {
  return <span className={cn("rounded px-2 py-0.5 capitalize", strong ? "bg-secondary text-foreground" : "text-muted-foreground border border-border")}>{children}</span>;
}

function WhatIf({ workers, stations, disabled }: { workers: Worker[]; stations: Stn[]; disabled: boolean }) {
  const [w, setW] = useState("");
  const [s, setS] = useState("");
  const [res, setRes] = useState<WhatIfResult | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Section title="What-if check">
      <div className="space-y-3 rounded-lg border border-border bg-card p-4">
        <p className="text-base text-muted-foreground">Check only — this changes nothing. Real moves happen through decisions or copilot proposals.</p>
        <Select value={w} onValueChange={(v) => { setW(v); setRes(null); }} disabled={disabled}>
          <SelectTrigger className="min-h-11 text-base"><SelectValue placeholder="Pick a worker" /></SelectTrigger>
          <SelectContent className="max-h-80">{workers.map((x) => <SelectItem key={x.id} value={x.id}>{x.name} · {x.id}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={s} onValueChange={(v) => { setS(v); setRes(null); }} disabled={disabled}>
          <SelectTrigger className="min-h-11 text-base"><SelectValue placeholder="Pick a station" /></SelectTrigger>
          <SelectContent className="max-h-80">{stations.map((x) => <SelectItem key={x.id} value={x.id}>{x.id} · {x.name}</SelectItem>)}</SelectContent>
        </Select>
        <Btn variant="primary" className="w-full" disabled={!w || !s || busy || disabled} onClick={async () => {
          setBusy(true);
          try { setRes(await api.whatif(w, s)); } catch { /* toast shown */ } finally { setBusy(false); }
        }}>{busy ? "Checking…" : "Check fit"}</Btn>
        {res && (
          <div className="space-y-1 border-t border-border pt-3">
            <div className="font-display text-2xl font-bold">{res.worker_name}: {res.from_station ?? "—"} → {res.to_station} · {res.ok ? "OK" : <span className="text-high">Not recommended</span>}</div>
            {res.warnings.map((x, i) => <p key={i} className="text-lg text-high">⚠ {x}</p>)}
            {res.benefits.map((x, i) => <p key={i} className="text-lg">✓ {x}</p>)}
          </div>
        )}
      </div>
    </Section>
  );
}
