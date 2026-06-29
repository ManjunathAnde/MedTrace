import { AlertTriangle } from "lucide-react";
import { Card } from "./Card";
import { InvestigationError } from "../hooks/useInvestigation";

export function ErrorCard({ error }: { error: InvestigationError }) {
  return (
    <Card className="border-red-100 bg-red-50/30 p-6 dark:border-red-950/70 dark:bg-red-950/20">
      <div className="flex gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-600 dark:bg-red-950/60 dark:text-red-300">
          <AlertTriangle size={22} />
        </div>
        <div>
          <div className="text-sm font-semibold text-red-700 dark:text-red-300">{error.status ? `Error ${error.status}` : "Unable to investigate"}</div>
          <h2 className="mt-1 text-xl font-bold text-slate-950 dark:text-slate-50">{error.title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-300">{error.message}</p>
        </div>
      </div>
    </Card>
  );
}
