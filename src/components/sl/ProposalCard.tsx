import { useState } from "react";
import { Bot } from "lucide-react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import type { Proposal } from "@/types";
import { ActBtn } from "./bits";

export function ProposalCard({ p, onDone }: { p: Proposal; onDone?: (status: Proposal["status"]) => void }) {
  const { act, showApplied } = useLive();
  const [busy, setBusy] = useState(false);
  const params = p.params as Record<string, unknown>;
  const detail = p.kind === "assign"
    ? `${String(params["worker"] ?? "")} → ${String(params["station"] ?? "")}`
    : `${String(params["decision"] ?? "")} · ${String(params["incident_id"] ?? "")}`;
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 text-sm uppercase tracking-wider text-muted-foreground">
        <Bot className="h-4 w-4" /> Copilot proposal · {p.kind === "assign" ? "assign" : "decision"}
        {p.status !== "pending" && <span className="ml-auto font-semibold text-foreground">{p.status}</span>}
      </div>
      <p className="mt-1 text-lg">{p.description}</p>
      <p className="font-display text-base text-muted-foreground">{detail}</p>
      {p.status === "pending" && (
        <div className="mt-3 flex gap-2">
          <ActBtn variant="primary" disabled={busy} onClick={async () => {
            setBusy(true);
            const r = await act(() => api.confirmProposal(p.id));
            setBusy(false);
            if (r) { showApplied("Proposal confirmed", r.applied); onDone?.("confirmed"); }
          }}>Confirm</ActBtn>
          <ActBtn variant="ghost" disabled={busy} onClick={async () => {
            setBusy(true);
            const r = await act(() => api.rejectProposal(p.id));
            setBusy(false);
            if (r) onDone?.("rejected");
          }}>Reject</ActBtn>
        </div>
      )}
    </div>
  );
}
