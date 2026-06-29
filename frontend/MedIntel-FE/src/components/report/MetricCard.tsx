import { LucideIcon } from "lucide-react";
import { cn } from "../../lib/utils";

type MetricCardProps = {
  label: string;
  value: number;
  icon: LucideIcon;
  tone: "red" | "amber" | "emerald" | "slate";
};

const tones = {
  red: "border-red-100 bg-red-50/50 text-red-700 dark:border-red-950/70 dark:bg-red-950/20 dark:text-red-300",
  amber: "border-amber-100 bg-amber-50/50 text-amber-700 dark:border-amber-950/70 dark:bg-amber-950/20 dark:text-amber-300",
  emerald: "border-emerald-100 bg-emerald-50/50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/20 dark:text-emerald-300",
  slate: "border-slate-200 bg-slate-50/70 text-slate-700 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-300",
};

export function MetricCard({ label, value, icon: Icon, tone }: MetricCardProps) {
  return (
    <div className={cn("flex h-32 min-w-0 flex-col items-center justify-center rounded-xl border p-4 text-center", tones[tone])}>
      <Icon size={22} className="shrink-0" />
      <div className="mt-3 text-2xl font-bold leading-none">{value}</div>
      <div className="mt-2 max-w-full whitespace-normal break-words text-sm font-semibold leading-tight">{label}</div>
    </div>
  );
}
