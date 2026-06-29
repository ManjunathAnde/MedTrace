import { motion } from "framer-motion";
import { LimitationsCard } from "./LimitationsCard";
import { SectionList } from "./SectionList";
import { SourcesCard } from "./SourcesCard";
import { SummaryCard } from "./SummaryCard";
import { ReportViewModel } from "./reportUtils";

const fadeUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
};

export function ReportSections({ report }: { report: ReportViewModel }) {
  return (
    <div className="space-y-5 p-5 sm:p-6">
      <motion.div {...fadeUp} transition={{ delay: 0.12, duration: 0.28 }}>
        <SummaryCard report={report} />
      </motion.div>
      {report.warnings.length > 0 && (
        <motion.div {...fadeUp} transition={{ delay: 0.24, duration: 0.28 }}>
          <SectionList title="Warnings" type="warnings" items={report.warnings} empty="No warnings were returned for this investigation." />
        </motion.div>
      )}
      {report.contraindications.length > 0 && (
        <motion.div {...fadeUp} transition={{ delay: 0.34, duration: 0.28 }}>
          <SectionList title="Contraindications" type="contraindications" items={report.contraindications} empty="No contraindications were returned for this investigation." />
        </motion.div>
      )}
      {report.interactions.length > 0 && (
        <motion.div {...fadeUp} transition={{ delay: 0.44, duration: 0.28 }}>
          <SectionList title="Interactions" type="interactions" items={report.interactions} empty="No interactions were returned for this investigation." />
        </motion.div>
      )}
      {report.adverseEvents.length > 0 && (
        <motion.div {...fadeUp} transition={{ delay: 0.54, duration: 0.28 }}>
          <SectionList title="Adverse Events" type="adverseEvents" items={report.adverseEvents} empty="No adverse events were returned for this investigation." />
        </motion.div>
      )}
      {report.recalls.length > 0 && (
        <motion.div {...fadeUp} transition={{ delay: 0.64, duration: 0.28 }}>
          <SectionList title="Recalls" type="recalls" items={report.recalls} empty="No recalls were returned for this investigation." />
        </motion.div>
      )}
      <motion.div {...fadeUp} transition={{ delay: 0.74, duration: 0.28 }}>
        <SourcesCard sources={report.sources} />
      </motion.div>
      {report.limitations.length > 0 && (
        <motion.div {...fadeUp} transition={{ delay: 0.84, duration: 0.28 }}>
          <LimitationsCard limitations={report.limitations} />
        </motion.div>
      )}
    </div>
  );
}
