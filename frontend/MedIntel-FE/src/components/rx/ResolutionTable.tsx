import { CheckCircle2, ExternalLink, SearchX } from "lucide-react";
import type { Resolution } from "../../api/types";
import { Card } from "../Card";
import { formatDate } from "../evidence/labels";

export function ResolutionTable({ resolution }: { resolution: Resolution[] }) {
  if (!resolution.length) return null;

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-lg font-bold text-slate-950 dark:text-slate-50">Medications checked</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-xs uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
            <tr className="border-b border-border">
              <th className="py-2 pr-4 font-semibold">You entered</th>
              <th className="py-2 pr-4 font-semibold">Resolved as</th>
              <th className="py-2 pr-4 font-semibold">Ingredients</th>
              <th className="py-2 font-semibold">FDA label used</th>
            </tr>
          </thead>
          <tbody>
            {resolution.map((entry) => (
              <tr key={entry.input_name} className="border-b border-border/70 align-top last:border-0">
                <td className="py-3 pr-4 font-medium text-slate-900 dark:text-slate-100">{entry.input_name}</td>
                {entry.status === "RESOLVED" ? (
                  <>
                    <td className="py-3 pr-4 text-slate-700 dark:text-slate-300">
                      <span className="inline-flex items-center gap-1.5">
                        <CheckCircle2 size={15} className="text-emerald-700 dark:text-emerald-300" />
                        {entry.preferred_name}
                      </span>
                      <div className="text-xs text-slate-500 dark:text-slate-400">RxCUI {entry.rxcui}</div>
                    </td>
                    <td className="py-3 pr-4 text-slate-700 dark:text-slate-300">{entry.ingredients.join(", ")}</td>
                    <td className="py-3 text-slate-700 dark:text-slate-300">
                      {entry.label ? (
                        <a href={entry.label.url} target="_blank" rel="noreferrer" className="font-medium text-emerald-800 underline decoration-emerald-300 underline-offset-2 hover:text-emerald-950 dark:text-emerald-300 dark:decoration-emerald-700">
                          {entry.label.title}
                          <ExternalLink size={12} className="ml-1 inline" />
                        </a>
                      ) : (
                        "No label retrieved"
                      )}
                      {entry.label && <div className="text-xs text-slate-500 dark:text-slate-400">Effective {formatDate(entry.label.effective_date)}</div>}
                    </td>
                  </>
                ) : (
                  <td colSpan={3} className="py-3 text-slate-600 dark:text-slate-400">
                    <span className="inline-flex items-center gap-1.5">
                      <SearchX size={15} className="text-slate-500" />
                      {entry.message}
                    </span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
