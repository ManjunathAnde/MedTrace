import { AlertTriangle, CircleSlash, Link2, ShieldAlert, Sparkles } from "lucide-react";
import { useState } from "react";
import { Card } from "../Card";
import { MetricCard } from "./MetricCard";
import { ReportViewModel, itemDescription } from "./reportUtils";

const COLLAPSED_SUMMARY_SENTENCES = 5;

function splitSentences(text: string) {
  return text.split(/(?<=[.!?])\s+/).filter(Boolean);
}

export function SummaryCard({ report }: { report: ReportViewModel }) {
  const metricCount = report.warnings.length + report.contraindications.length + report.interactions.length + report.adverseEvents.length;
  const [isExpanded, setIsExpanded] = useState(false);
  const summarySentences = splitSentences(report.summary);
  const shouldCollapse = !report.isSynthesisUnavailable && summarySentences.length > COLLAPSED_SUMMARY_SENTENCES;
  const displayedSummary = shouldCollapse && !isExpanded ? summarySentences.slice(0, COLLAPSED_SUMMARY_SENTENCES).join(" ") : report.summary;

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="mb-3 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
            <Sparkles size={19} />
          </div>
          <h3 className="text-lg font-bold text-slate-950 dark:text-slate-50">AI Risk Summary</h3>
        </div>
        {report.isSynthesisUnavailable ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
            Evidence retrieval succeeded, but AI report synthesis is temporarily unavailable. Try again shortly to generate the narrative report.
          </div>
        ) : (
          <>
            <p className="leading-7 text-slate-700 dark:text-slate-300">{displayedSummary}</p>
            {shouldCollapse && (
              <button
                type="button"
                onClick={() => setIsExpanded((value) => !value)}
                className="mt-3 text-sm font-semibold text-emerald-800 transition hover:text-emerald-950 dark:text-emerald-300 dark:hover:text-emerald-200"
              >
                {isExpanded ? "Show Less" : "Show More"}
              </button>
            )}
          </>
        )}

        {metricCount > 0 && (
          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {report.warnings.length > 0 && <MetricCard label="Warnings" value={report.warnings.length} icon={AlertTriangle} tone="red" />}
            {report.contraindications.length > 0 && <MetricCard label="Contraindications" value={report.contraindications.length} icon={CircleSlash} tone="amber" />}
            {report.interactions.length > 0 && <MetricCard label="Interactions" value={report.interactions.length} icon={Link2} tone="emerald" />}
            {report.adverseEvents.length > 0 && <MetricCard label="Adverse Events" value={report.adverseEvents.length} icon={ShieldAlert} tone="slate" />}
          </div>
        )}
      </Card>

      {report.keyFindings.length > 0 && (
        <Card className="p-5">
          <h3 className="text-lg font-bold text-slate-950 dark:text-slate-50">Key Findings</h3>
          <ul className="mt-4 space-y-3">
            {report.keyFindings.map((finding, index) => (
              <li key={`finding-${index}`} className="flex gap-3 text-sm leading-6 text-slate-700 dark:text-slate-300">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-700" />
                {itemDescription(finding)}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
