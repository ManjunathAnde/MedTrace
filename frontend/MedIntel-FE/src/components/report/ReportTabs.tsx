import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CircleSlash, Database, Home, Link2, RotateCcw, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "../../lib/utils";
import { SectionList } from "./SectionList";
import { SourcesCard } from "./SourcesCard";
import { SummaryCard } from "./SummaryCard";
import { ReportSectionKey, ReportViewModel } from "./reportUtils";

const tabs = [
  { key: "summary", label: "Summary", icon: Home },
  { key: "warnings", label: "Warnings", icon: AlertTriangle },
  { key: "contraindications", label: "Contraindications", icon: CircleSlash },
  { key: "interactions", label: "Interactions", icon: Link2 },
  { key: "adverseEvents", label: "Adverse Events", icon: ShieldAlert },
  { key: "recalls", label: "Recalls", icon: RotateCcw },
  { key: "sources", label: "Sources", icon: Database },
] satisfies { key: ReportSectionKey; label: string; icon: typeof Home }[];

export function ReportTabs({ report }: { report: ReportViewModel }) {
  const visibleTabs = useMemo(() => tabs, []);
  const [active, setActive] = useState<ReportSectionKey>("summary");

  return (
    <div>
      <div className="flex gap-2 overflow-x-auto border-b border-border px-4 sm:px-6">
        {visibleTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActive(tab.key)}
            className={cn(
              "relative flex h-14 shrink-0 items-center gap-2 px-3 text-sm font-medium transition",
              active === tab.key ? "text-emerald-800" : "text-slate-600 hover:text-slate-950",
            )}
          >
            <tab.icon size={17} />
            {tab.label}
            {active === tab.key && <motion.span layoutId="active-tab" className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-emerald-700" />}
          </button>
        ))}
      </div>
      <div className="p-5 sm:p-6">
        <AnimatePresence mode="wait">
          <motion.div key={active} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.18 }}>
            {active === "summary" && <SummaryCard report={report} />}
            {active === "warnings" && <SectionList title="Warnings" type="warnings" items={report.warnings} empty="No warnings were returned for this investigation." />}
            {active === "contraindications" && <SectionList title="Contraindications" type="contraindications" items={report.contraindications} empty="No contraindications were returned for this investigation." />}
            {active === "interactions" && <SectionList title="Interactions" type="interactions" items={report.interactions} empty="No interactions were returned for this investigation." />}
            {active === "adverseEvents" && <SectionList title="Adverse Events" type="adverseEvents" items={report.adverseEvents} empty="No adverse events were returned for this investigation." />}
            {active === "recalls" && <SectionList title="Recalls" type="recalls" items={report.recalls} empty="No recalls were returned for this investigation." />}
            {active === "sources" && <SourcesCard sources={report.sources} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
