import { createFileRoute } from "@tanstack/react-router";
import { ShieldAlert, UserX } from "lucide-react";
import { useLive } from "@/lib/live";
import { cn } from "@/lib/utils";
import { sevBorder } from "@/components/sl/bits";
import type { SensorView, StationView, ZoneView } from "@/types";

export const Route = createFileRoute("/line")({
  head: () => ({
    meta: [
      { title: "Line · ShiftLoop Supervisor" },
      { name: "description", content: "Zones A–D and stations S01–S24: status, coverage, qualification flags and sensors." },
      { property: "og:title", content: "Line · ShiftLoop Supervisor" },
      { property: "og:description", content: "Live floor view of the assembly section." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: LinePage,
});

const LEVEL = ["untrained", "trainee", "qualified", "trainer"];

function LinePage() {
  const { snap } = useLive();
  if (!snap) return null;
  return (
    <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
      {snap.zones.map((z) => (
        <ZoneCol key={z.id} zone={z} stations={snap.stations.filter((s) => s.zone === z.id)} />
      ))}
    </div>
  );
}

function ZoneCol({ zone, stations }: { zone: ZoneView; stations: StationView[] }) {
  return (
    <section className={cn("flex flex-col rounded-lg border border-border border-t-8 bg-card", zone.alert === "critical" ? "border-t-critical" : zone.alert === "high" ? "border-t-high" : zone.alert === "medium" ? "border-t-medium" : "border-t-border")}>
      <div className="flex items-baseline justify-between p-3">
        <h2 className="font-display text-4xl font-bold">Zone {zone.id}</h2>
        <span className="font-display text-xl text-muted-foreground">{zone.people} people</span>
      </div>
      <div className="grid flex-1 grid-cols-2 gap-2 px-3">
        {stations.map((s) => <StationTile key={s.id} s={s} />)}
      </div>
      <div className="mt-3 space-y-2 border-t border-border p-3 text-base">
        <Row label="Fire wardens" v={zone.fire_wardens} />
        <Row label="First aiders" v={zone.first_aiders} />
        <div><span className="text-muted-foreground">Exits </span>{zone.exits.join(" · ")} <span className="text-muted-foreground">· AP </span>{zone.assembly_point}</div>
        <div className="space-y-1 pt-1">
          {zone.sensors.map((x) => <Sensor key={x.id} x={x} />)}
        </div>
      </div>
    </section>
  );
}

function Row({ label, v }: { label: string; v: string[] }) {
  return (
    <div>
      <span className="text-muted-foreground">{label} </span>
      {v.length ? v.join(", ") : <span className="font-semibold text-high">none in zone</span>}
    </div>
  );
}

function Sensor({ x }: { x: SensorView }) {
  const st = x.value == null ? "none" : x.value >= x.crit ? "crit" : x.value >= x.warn ? "warn" : "ok";
  return (
    <div className={cn("flex items-baseline justify-between rounded px-2 py-1", st === "crit" && "bg-critical text-critical-foreground", st === "warn" && "bg-medium/15 text-medium")}>
      <span className="font-mono text-sm">{x.id}{x.station ? ` · ${x.station}` : ""}</span>
      <span className="font-display text-lg font-bold tabular-nums">{x.value == null ? "—" : `${x.value.toFixed(1)} ${x.unit}`}</span>
    </div>
  );
}

function StationTile({ s }: { s: StationView }) {
  const slow = s.cycle_time_s != null && s.cycle_time_s > 0 && s.cycle_time_s > s.takt_s;
  const lowLevel = s.operator && s.operator.level <= 1;
  return (
    <div className={cn("rounded-md border border-border border-l-4 bg-background p-2", sevBorder(s.alert), s.alert === "critical" && "bg-critical/10")}>
      <div className="flex items-center gap-1">
        <span className="font-display text-2xl font-bold">{s.id}</span>
        {s.safety_critical && <ShieldAlert className="h-4 w-4 text-muted-foreground" aria-label="Safety-critical station" />}
        <span className={cn("ml-auto rounded px-1.5 text-xs font-semibold uppercase", s.status === "running" ? "text-muted-foreground" : "bg-secondary text-foreground")}>{s.status}</span>
      </div>
      <div className="truncate text-xs text-muted-foreground">{s.name}</div>
      {s.operator ? (
        <div className="mt-1 text-sm">
          <span className="font-medium">{s.operator.name}</span>
          {lowLevel && <span className="ml-1 rounded bg-medium px-1 text-xs font-bold uppercase text-medium-foreground">{LEVEL[s.operator.level]}</span>}
        </div>
      ) : (
        <div className="mt-1 inline-flex items-center gap-1 rounded bg-high px-1.5 text-sm font-bold uppercase text-high-foreground"><UserX className="h-4 w-4" /> Uncovered</div>
      )}
      <div className={cn("mt-1 font-display text-base tabular-nums", slow ? "font-bold text-medium" : "text-muted-foreground")}>
        {s.cycle_time_s ? `${s.cycle_time_s.toFixed(0)}s` : "—"} / {s.takt_s.toFixed(0)}s
        {s.defects > 0 && <span className="ml-2 text-foreground">{s.defects} defects</span>}
      </div>
    </div>
  );
}
