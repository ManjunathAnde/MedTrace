import { cn } from "../lib/utils";

type MedTraceLogoProps = {
  className?: string;
  compact?: boolean;
};

export function MedTraceLogo({ className, compact = false }: MedTraceLogoProps) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-2xl border border-emerald-200 bg-emerald-50 text-emerald-800 shadow-card transition-colors dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300",
        compact ? "h-8 w-8 rounded-lg" : "h-14 w-14",
        className,
      )}
      aria-hidden="true"
    >
      <svg viewBox="0 0 64 64" className={compact ? "h-6 w-6" : "h-11 w-11"} fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M30.5 5.5C23.4 9.5 16.1 11.8 9 12.7v15.1c0 13.4 7.8 24.9 21.5 31.2 13.7-6.3 21.5-17.8 21.5-31.2V12.7c-7.1-.9-14.4-3.2-21.5-7.2Z"
          className="stroke-current"
          strokeWidth="4"
          strokeLinejoin="round"
        />
        <path d="M15.5 25.5h12.8" className="stroke-current" strokeWidth="2.8" strokeLinecap="round" />
        <path d="M15.5 33.5h9.7" className="stroke-current" strokeWidth="2.8" strokeLinecap="round" />
        <path d="M15.5 41.5h13" className="stroke-current" strokeWidth="2.8" strokeLinecap="round" />
        <circle cx="14" cy="25.5" r="2.5" className="fill-emerald-50 stroke-current dark:fill-emerald-950" strokeWidth="2.2" />
        <circle cx="14" cy="33.5" r="2.5" className="fill-emerald-50 stroke-current dark:fill-emerald-950" strokeWidth="2.2" />
        <circle cx="14" cy="41.5" r="2.5" className="fill-emerald-50 stroke-current dark:fill-emerald-950" strokeWidth="2.2" />
        <path
          d="M27.2 43.8 41.9 20c2.4-3.9 7.5-5.1 11.4-2.7 3.9 2.4 5.1 7.5 2.7 11.4L41.3 52.5c-2.4 3.9-7.5 5.1-11.4 2.7-3.9-2.4-5.1-7.5-2.7-11.4Z"
          className="fill-emerald-700 stroke-emerald-50 dark:fill-emerald-400 dark:stroke-slate-950"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <path d="m35.4 31.2 11.8 7.3" className="stroke-emerald-50 dark:stroke-slate-950" strokeWidth="3" strokeLinecap="round" />
        <circle cx="47" cy="47" r="11" className="fill-white stroke-current dark:fill-slate-950" strokeWidth="4" />
        <path d="M47 41.5v11M41.5 47h11" className="stroke-current" strokeWidth="4" strokeLinecap="round" />
        <path d="m55.3 55.3 6.2 6.2" className="stroke-current" strokeWidth="4" strokeLinecap="round" />
      </svg>
    </div>
  );
}
