import { AlertTriangle, CircleSlash, Link2, ShieldAlert, Sparkles } from "lucide-react";
import { Card } from "../Card";
import { MetricCard } from "./MetricCard";
import { ReportViewModel, itemDescription } from "./reportUtils";

export function SummaryCard({ report }: { report: ReportViewModel }) {
  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="mb-3 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
            <Sparkles size={19} />
          </div>
          <h3 className="text-lg font-bold text-slate-950 dark:text-slate-50">AI Risk Summary</h3>
        </div>
        <p className="leading-7 text-slate-700 dark:text-slate-300">{report.summary}</p>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Warnings" value={report.warnings.length} icon={AlertTriangle} tone="red" />
          <MetricCard label="Contraindications" value={report.contraindications.length} icon={CircleSlash} tone="amber" />
          <MetricCard label="Interactions" value={report.interactions.length} icon={Link2} tone="emerald" />
          <MetricCard label="Adverse Events" value={report.adverseEvents.length} icon={ShieldAlert} tone="slate" />
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="text-lg font-bold text-slate-950 dark:text-slate-50">Key Findings</h3>
        {report.keyFindings.length ? (
          <ul className="mt-4 space-y-3">
            {report.keyFindings.map((finding, index) => (
              <li key={`finding-${index}`} className="flex gap-3 text-sm leading-6 text-slate-700 dark:text-slate-300">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-700" />
                {itemDescription(finding)}
              </li>
            ))}
          </ul>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-border bg-slate-50/60 p-6 text-sm text-slate-500 dark:bg-slate-900/50 dark:text-slate-400">
            No key findings were returned for this investigation.
          </div>
        )}
      </Card>
    </div>
  );
}
