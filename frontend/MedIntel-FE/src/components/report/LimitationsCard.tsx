import { Info } from "lucide-react";
import { Card } from "../Card";
import { itemDescription } from "./reportUtils";

export function LimitationsCard({ limitations }: { limitations: unknown[] }) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-50 text-slate-700 dark:bg-slate-900 dark:text-slate-300">
          <Info size={19} />
        </div>
        <h3 className="text-lg font-bold text-slate-950 dark:text-slate-50">Limitations</h3>
      </div>
      {limitations.length ? (
        <ul className="space-y-3">
          {limitations.map((limitation, index) => (
            <li key={`limitation-${index}`} className="flex gap-3 text-sm leading-6 text-slate-700 dark:text-slate-300">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
              {itemDescription(limitation)}
            </li>
          ))}
        </ul>
      ) : (
        <div className="rounded-lg border border-dashed border-border bg-slate-50/60 p-6 text-sm text-slate-500 dark:bg-slate-900/50 dark:text-slate-400">
          No additional limitations were returned by the API.
        </div>
      )}
    </Card>
  );
}
