import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Btn } from "./bits";

export function ReasonDialog({
  open, onOpenChange, title, description, confirmLabel, onConfirm, danger,
}: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string;
  confirmLabel: string; onConfirm: (reason: string) => Promise<void> | void; danger?: boolean;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) setReason(""); onOpenChange(o); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">{title}</DialogTitle>
          {description && <DialogDescription className="text-base">{description}</DialogDescription>}
        </DialogHeader>
        <Textarea autoFocus value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Short reason (required)" className="min-h-24 text-lg" />
        <div className="flex justify-end gap-2">
          <Btn onClick={() => onOpenChange(false)}>Cancel</Btn>
          <Btn
            variant={danger ? "danger" : "primary"}
            disabled={!reason.trim() || busy}
            onClick={async () => { setBusy(true); try { await onConfirm(reason.trim()); setReason(""); } finally { setBusy(false); } }}
          >
            {busy ? "Sending…" : confirmLabel}
          </Btn>
        </div>
      </DialogContent>
    </Dialog>
  );
}
