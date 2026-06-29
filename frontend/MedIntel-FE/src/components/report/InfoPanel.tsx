import { Clock3, Gauge, Pill, ShieldPlus } from "lucide-react";
import { Card } from "../Card";
import { SourcesCard } from "./SourcesCard";
import { ReportViewModel } from "./reportUtils";

function Detail({ label, value, icon: Icon }: { label: string; value?: string; icon: typeof Pill }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
        <Icon size={16} />
        {label}
      </span>
      <span className="text-right font-medium text-slate-800 dark:text-slate-200">{value || "Not available"}</span>
    </div>
  );
}

export function InfoPanel({ report }: { report: ReportViewModel }) {
  return (
    <aside className="space-y-5">
      <Card className="p-5">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
            <ShieldPlus size={19} />
          </div>
          <h3 className="font-bold text-slate-950 dark:text-slate-50">Investigation Details</h3>
        </div>
        <div className="space-y-4">
          <Detail label="Medication" value={report.drugName} icon={Pill} />
          <Detail label="Profile Used" value={report.profileUsed} icon={ShieldPlus} />
          <Detail label="Completeness Score" value={report.completenessScore} icon={Gauge} />
          <Detail label="Duration" value={report.duration} icon={Clock3} />
        </div>
      </Card>
      <SourcesCard sources={report.sources} compact />
      <Card className="bg-emerald-50/50 p-5 dark:bg-emerald-950/20">
        <div className="flex gap-3">
          <ShieldPlus className="mt-0.5 shrink-0 text-emerald-700 dark:text-emerald-300" size={20} />
          <p className="text-sm leading-6 text-slate-700 dark:text-slate-300">This information is for educational purposes only. Always consult healthcare professionals for medical advice.</p>
        </div>
      </Card>
    </aside>
  );
}
