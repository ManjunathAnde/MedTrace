import { LucideIcon } from "lucide-react";
import { ReactNode } from "react";
import { cn } from "../lib/utils";
import { Card } from "./Card";

export type StatusTone = "emerald" | "sky" | "amber" | "slate";

const tones: Record<StatusTone, { card: string; icon: string; eyebrow: string }> = {
  emerald: {
    card: "border-emerald-100 bg-emerald-50/30 dark:border-emerald-900/60 dark:bg-emerald-950/20",
    icon: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300",
    eyebrow: "text-emerald-700 dark:text-emerald-300",
  },
  sky: {
    card: "border-sky-100 bg-sky-50/40 dark:border-sky-900/60 dark:bg-sky-950/20",
    icon: "bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300",
    eyebrow: "text-sky-700 dark:text-sky-300",
  },
  amber: {
    card: "border-amber-100 bg-amber-50/40 dark:border-amber-900/60 dark:bg-amber-950/20",
    icon: "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300",
    eyebrow: "text-amber-700 dark:text-amber-300",
  },
  slate: {
    card: "",
    icon: "bg-slate-100 text-slate-700 dark:bg-slate-900 dark:text-slate-300",
    eyebrow: "text-slate-500 dark:text-slate-400",
  },
};

type StatusCardProps = {
  tone: StatusTone;
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  message?: string | null;
  children?: ReactNode;
};

// One card per non-answer status (Section 11 item 7); same shape as ErrorCard.
export function StatusCard({ tone, icon: Icon, eyebrow, title, message, children }: StatusCardProps) {
  const style = tones[tone];
  return (
    <Card className={cn("p-6", style.card)}>
      <div className="flex gap-4">
        <div className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-lg", style.icon)}>
          <Icon size={22} />
        </div>
        <div className="min-w-0 flex-1">
          <div className={cn("text-sm font-semibold", style.eyebrow)}>{eyebrow}</div>
          <h2 className="mt-1 text-xl font-bold text-slate-950 dark:text-slate-50">{title}</h2>
          {message && <p className="mt-2 max-w-2xl whitespace-pre-line text-sm leading-6 text-slate-600 dark:text-slate-300">{message}</p>}
          {children && <div className="mt-4">{children}</div>}
        </div>
      </div>
    </Card>
  );
}
