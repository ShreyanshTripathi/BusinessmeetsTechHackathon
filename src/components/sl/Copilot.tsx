import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/live";
import type { Language, Proposal } from "@/types";
import { Btn } from "./bits";
import { ProposalCard } from "./ProposalCard";
import { Textarea } from "@/components/ui/textarea";

type Msg = { role: "user" | "assistant"; content: string; proposals?: Proposal[]; error?: boolean };
const STARTERS = ["Who can cover S12?", "Is zone C safe?", "Which station caused the most downtime?", "Summarise the shift for the handover"];

export function LangPicker({ value, onChange }: { value: Language; onChange: (l: Language) => void }) {
  return (
    <div className="inline-flex rounded-md border border-input">
      {(["en", "de", "pl"] as Language[]).map((l) => (
        <button key={l} onClick={() => onChange(l)} className={`min-h-11 min-w-12 px-3 font-display text-lg uppercase ${value === l ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}>{l}</button>
      ))}
    </div>
  );
}

export function Copilot() {
  const { snap, demo } = useLive();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [lang, setLang] = useState<Language>("en");
  const [pending, setPending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, pending]);

  const send = async (text: string) => {
    const t = text.trim();
    if (!t || pending || demo) return;
    const history = msgs.filter((m) => !m.error).map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { role: "user", content: t }]);
    setInput("");
    setPending(true);
    try {
      const r = await api.chat(t, history, lang);
      setMsgs((m) => [...m, { role: "assistant", content: r.reply, proposals: r.proposals }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", content: (e as Error).message || "No answer", error: true }]);
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border p-4">
        <div>
          <div className="font-display text-2xl font-bold">Copilot</div>
          <div className="text-sm text-muted-foreground">Proposes only · you confirm{snap?.mode === "offline" ? " · offline mode" : ""}</div>
        </div>
        <LangPicker value={lang} onChange={setLang} />
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {msgs.length === 0 && (
          <div className="space-y-3">
            <p className="text-muted-foreground">Ask about coverage, safety or downtime. Answers can take a few seconds; the plant clock pauses meanwhile.</p>
            <div className="flex flex-wrap gap-2">
              {STARTERS.map((s) => (
                <Btn key={s} disabled={demo} className="text-base" onClick={() => send(s)}>{s}</Btn>
              ))}
            </div>
            {demo && <p className="text-sm text-muted-foreground">Connect a backend to chat.</p>}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "ml-8 rounded-lg bg-secondary p-3 text-lg" : "mr-4 space-y-2"}>
            {m.role === "assistant" ? (
              <>
                <p className={`whitespace-pre-wrap text-lg ${m.error ? "text-high" : ""}`}>{m.content}</p>
                {m.proposals?.map((p) => <LiveProposal key={p.id} p={p} />)}
              </>
            ) : m.content}
          </div>
        ))}
        {pending && <div className="animate-pulse text-lg text-muted-foreground">Copilot is thinking… (up to 60 s)</div>}
        <div ref={endRef} />
      </div>
      <form className="flex gap-2 border-t border-border p-3" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <Textarea
          value={input} onChange={(e) => setInput(e.target.value)} placeholder={demo ? "Connect a backend to chat" : "Ask the copilot…"}
          disabled={demo} rows={1} className="min-h-11 flex-1 resize-none text-lg"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
        />
        <Btn variant="primary" type="submit" disabled={pending || demo || !input.trim()} aria-label="Send"><Send className="h-5 w-5" /></Btn>
      </form>
    </div>
  );
}

/** Show proposal with live status if it is still pending in the snapshot. */
function LiveProposal({ p }: { p: Proposal }) {
  const { snap } = useLive();
  const [status, setStatus] = useState(p.status);
  const inSnap = snap?.proposals.some((x) => x.id === p.id);
  const effective = status === "pending" && !inSnap && snap ? "pending" : status;
  return <ProposalCard p={{ ...p, status: effective }} onDone={setStatus} />;
}
