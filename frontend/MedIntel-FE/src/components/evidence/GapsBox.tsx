import { Info } from "lucide-react";

export function GapsBox({ gaps, title = "Not covered by the retrieved FDA sources:" }: { gaps: string[]; title?: string }) {
  if (!gaps.length) return null;
  return (
    <div className="rounded-lg border border-border bg-slate-50/70 p-4 text-sm leading-6 text-slate-600 dark:bg-slate-900/50 dark:text-slate-400">
      <div className="flex items-center gap-2 font-semibold text-slate-700 dark:text-slate-300">
        <Info size={16} />
        {title}
      </div>
      <ul className="mt-2 list-disc space-y-1 pl-6">
        {gaps.map((gap) => (
          <li key={gap}>{gap}</li>
        ))}
      </ul>
    </div>
  );
}
