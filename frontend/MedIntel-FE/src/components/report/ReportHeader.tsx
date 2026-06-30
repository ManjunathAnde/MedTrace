import { motion } from "framer-motion";
import { Pill, ShieldCheck } from "lucide-react";
import { ReportViewModel } from "./reportUtils";

export function ReportHeader({ report }: { report: ReportViewModel }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="flex flex-col gap-5 border-b border-border p-6 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-emerald-700 text-white dark:bg-emerald-500 dark:text-emerald-950">
          <Pill size={28} />
        </div>
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-3xl font-bold text-slate-950 dark:text-slate-50">{report.drugName}</h2>
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
              <ShieldCheck size={14} />
              Investigation Complete
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
            <span>Profile Used: {report.profileUsed}</span>
            <span>Completeness Score: {report.completenessScore}</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
