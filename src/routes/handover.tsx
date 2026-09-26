import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import { ActBtn, Btn, Section } from "@/components/sl/bits";
import { LangPicker } from "@/components/sl/Copilot";
import { Textarea } from "@/components/ui/textarea";
import type { Language } from "@/types";

export const Route = createFileRoute("/handover")({
  head: () => ({
    meta: [
      { title: "Shift handover · ShiftLoop Supervisor" },
      { name: "description", content: "Generate, edit and copy the shift handover in English, German or Polish." },
      { property: "og:title", content: "Shift handover · ShiftLoop Supervisor" },
      { property: "og:description", content: "Editable shift handover notes." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: HandoverPage,
});

function HandoverPage() {
  const { demo } = useLive();
  const [lang, setLang] = useState<Language>("en");
  const [text, setText] = useState("");
  const [mode, setMode] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="mx-auto max-w-4xl">
      <Section title="Shift handover" right={<LangPicker value={lang} onChange={setLang} />}>
        <div className="flex flex-wrap items-center gap-2">
          <ActBtn variant="primary" disabled={busy} onClick={async () => {
            if (demo) return;
            setBusy(true);
            try { const r = await api.handover(lang); setText(r.text); setMode(r.mode); } catch { /* toast */ } finally { setBusy(false); }
          }}>{busy ? "Writing… (up to 60 s)" : text ? "Regenerate" : "Generate handover"}</ActBtn>
          <Btn disabled={!text} onClick={async () => { await navigator.clipboard.writeText(text); toast.success("Copied"); }}>Copy</Btn>
          {mode && <span className="text-sm text-muted-foreground">Written in {mode} mode · edit freely before sharing</span>}
        </div>
        <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="The handover text appears here. The plant clock pauses while it is written." className="min-h-[50vh] text-lg leading-relaxed" />
      </Section>
    </div>
  );
}
