import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Pause, Play } from "lucide-react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { ActBtn, Btn, Section } from "@/components/sl/bits";
import { Input } from "@/components/ui/input";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Demo controls & backend · ShiftLoop Supervisor" },
      { name: "description", content: "Simulation controls, backend connection and voice alert settings." },
      { property: "og:title", content: "Demo controls & backend · ShiftLoop Supervisor" },
      { property: "og:description", content: "Configure the ShiftLoop dashboard." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const { snap, act, apiBase, changeApiBase, conn, demo, voiceOn, setVoiceOn, testVoice } = useLive();
  const [url, setUrl] = useState("");
  const [reset, setReset] = useState(false);
  useEffect(() => setUrl(apiBase), [apiBase]);
  const sim = snap?.sim;

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <Section title="Demo simulation">
        <div className="space-y-4 rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-3 font-display text-2xl font-bold">
            {sim?.running ? "Running" : "PAUSED"} <span className="text-lg font-normal text-muted-foreground">· {sim?.speed ?? "–"} plant min / s · {sim?.scenario}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {sim?.running
              ? <ActBtn variant="primary" onClick={() => act(() => api.sim({ action: "pause" }))}><Pause className="h-5 w-5" /> Pause</ActBtn>
              : <ActBtn variant="primary" onClick={() => act(() => api.sim({ action: "start" }))}><Play className="h-5 w-5" /> Play</ActBtn>}
            <ActBtn onClick={() => act(() => api.sim({ action: "step", minutes: 15 }))}>+15 min</ActBtn>
            <ActBtn variant="ghost" onClick={() => setReset(true)}>Reset</ActBtn>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground">Speed</span>
            {[1, 2, 5, 10, 30].map((n) => (
              <ActBtn key={n} className={sim?.speed === n ? "bg-secondary" : ""} onClick={() => act(() => api.sim({ action: "speed", speed: n }))}>{n}×</ActBtn>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Backend">
        <div className="space-y-3 rounded-lg border border-border bg-card p-4">
          <div className="text-base">Status: <span className="font-semibold">{demo ? "Not connected (demo data)" : conn}</span> · {snap?.mode === "offline" ? "Copilot offline mode" : snap ? "Copilot: Claude" : ""}</div>
          <div className="text-base text-muted-foreground">Current: <span className="font-mono">{apiBase || "(same origin)"}</span></div>
          <div className="flex flex-wrap gap-2">
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-backend.example.com" className="min-h-11 flex-1 text-base" />
            <Btn variant="primary" onClick={() => changeApiBase(url)}>Save</Btn>
            <Btn onClick={() => { setUrl(""); changeApiBase(null); }}>Clear</Btn>
          </div>
          <p className="text-sm text-muted-foreground">Tip: open the dashboard with <span className="font-mono">?api=https://…</span> to set this once.</p>
        </div>
      </Section>

      <Section title="Voice alerts">
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card p-4">
          <span className="text-lg">Voice alerts are <b>{voiceOn ? "on" : "off"}</b></span>
          <Btn variant="primary" onClick={() => setVoiceOn(!voiceOn)}>{voiceOn ? "Mute" : "Enable voice alerts"}</Btn>
          <Btn onClick={testVoice}>Test voice</Btn>
        </div>
      </Section>

      <AlertDialog open={reset} onOpenChange={setReset}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset the demo shift?</AlertDialogTitle>
            <AlertDialogDescription>The simulation restarts at 06:00 and stays paused.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="min-h-11">Cancel</AlertDialogCancel>
            <AlertDialogAction className="min-h-11" onClick={() => act(() => api.sim({ action: "reset", scenario: "demo" }))}>Reset</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
