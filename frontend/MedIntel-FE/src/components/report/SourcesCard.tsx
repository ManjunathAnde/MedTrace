import { CheckCircle2, Database } from "lucide-react";
import { Card } from "../Card";
import { itemTitle, renderValue } from "./reportUtils";

const fallbackSources = ["RxNorm", "DailyMed", "FDA Recall", "OpenFDA"];

export function SourcesCard({ sources, compact = false }: { sources: unknown[]; compact?: boolean }) {
  const sourceList = sources.length ? sources : fallbackSources;

  return (
    <Card className={compact ? "p-5" : "p-6"}>
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
          <Database size={19} />
        </div>
        <h3 className="font-bold text-slate-950 dark:text-slate-50">Data Sources{sources.length ? ` (${sources.length})` : ""}</h3>
      </div>
      <div className="space-y-3">
        {sourceList.map((source, index) => (
          <div key={`${itemTitle(source, "source")}-${index}`} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex min-w-0 items-center gap-2 font-medium text-slate-700 dark:text-slate-300">
              <CheckCircle2 className="shrink-0 text-emerald-700 dark:text-emerald-300" size={17} />
              <span className="truncate">{itemTitle(source, String(source))}</span>
            </span>
            {!compact && <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300">{renderValue(source).slice(0, 24)}</span>}
          </div>
        ))}
      </div>
    </Card>
  );
}
