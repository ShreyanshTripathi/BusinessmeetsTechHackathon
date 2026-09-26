import type { ReactNode, ButtonHTMLAttributes } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useLive } from "@/lib/live";
import { cn } from "@/lib/utils";
import type { Severity } from "@/types";

export function sevClasses(s: Severity | "warning" | null | undefined, solid = false) {
  switch (s) {
    case "critical":
      return solid ? "bg-critical text-critical-foreground" : "border-critical text-critical";
    case "high":
      return solid ? "bg-high text-high-foreground" : "border-high text-high";
    case "medium":
    case "warning":
      return solid ? "bg-medium text-medium-foreground" : "border-medium text-medium";
    default:
      return solid ? "bg-secondary text-secondary-foreground" : "border-border text-muted-foreground";
  }
}
export function sevBorder(s: Severity | "warning" | null | undefined) {
  if (s === "critical") return "border-l-critical";
  if (s === "high") return "border-l-high";
  if (s === "medium" || s === "warning") return "border-l-medium";
  return "border-l-border";
}

export function SevBadge({ s }: { s: Severity | "warning" | null }) {
  if (!s) return null;
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 font-display text-sm font-bold uppercase tracking-wide", sevClasses(s, true))}>
      {s}
    </span>
  );
}

export function Code({ code, className }: { code: string | null | undefined; className?: string }) {
  if (!code) return null;
  return <span className={cn("rounded border border-current px-2 py-0.5 font-mono text-lg font-bold tracking-wider", className)}>{code}</span>;
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "outline"; big?: boolean };

/** Action button: disabled in demo mode with tooltip. Always ≥44px. */
export function ActBtn({ variant = "outline", big, className, children, disabled, ...rest }: BtnProps) {
  const { demo } = useLive();
  const cls = cn(
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 font-display text-lg font-semibold tracking-wide transition-colors disabled:cursor-not-allowed disabled:opacity-45",
    big && "min-h-14 px-6 text-xl",
    variant === "primary" && "bg-primary text-primary-foreground hover:bg-primary/85",
    variant === "danger" && "bg-critical text-critical-foreground hover:bg-critical/85",
    variant === "outline" && "border border-input bg-transparent hover:bg-accent",
    variant === "ghost" && "hover:bg-accent",
    className,
  );
  if (demo) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0} className="inline-flex">
            <button {...rest} disabled className={cls}>{children}</button>
          </span>
        </TooltipTrigger>
        <TooltipContent>Connect a backend to act</TooltipContent>
      </Tooltip>
    );
  }
  return <button {...rest} disabled={disabled} className={cls}>{children}</button>;
}

export function Btn({ variant = "outline", big, className, children, ...rest }: BtnProps) {
  return (
    <button
      {...rest}
      className={cn(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 font-display text-lg font-semibold tracking-wide transition-colors disabled:opacity-45",
        big && "min-h-14 px-6 text-xl",
        variant === "primary" && "bg-primary text-primary-foreground hover:bg-primary/85",
        variant === "danger" && "bg-critical text-critical-foreground hover:bg-critical/85",
        variant === "outline" && "border border-input hover:bg-accent",
        variant === "ghost" && "hover:bg-accent",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Section({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-xl font-bold uppercase tracking-wider text-muted-foreground">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-dashed border-border px-5 py-6 text-lg text-muted-foreground">{children}</div>;
}

export const ACTION_LABEL: Record<string, string> = {
  emergency: "EMERGENCY", stop: "Stop", slow: "Slow down", reroute: "Reroute", keep_running: "Keep running",
};
export const AGENT_LABEL: Record<string, string> = { staffing: "Staffing", assembly: "Assembly", safety: "Fire & Safety" };
export const agentLabel = (a: string) => AGENT_LABEL[a] ?? a;
export const HARD_RULE_LABEL: Record<string, string> = { safety_stop: "Safety rule", quality_spread: "Quality rule" };
