import { motion } from "framer-motion";
import { AskResult } from "../components/ask/AskResult";
import { ErrorCard } from "../components/ErrorCard";
import { LoadingTimeline } from "../components/LoadingTimeline";
import { MockModeHint } from "../components/MockModeHint";
import { SearchHero } from "../components/SearchHero";
import { useInvestigation } from "../hooks/useInvestigation";

export function InvestigatePage({ onOpenPrescriptionCheck }: { onOpenPrescriptionCheck: (drugs: string[]) => void }) {
  const { report, error, loading, investigate } = useInvestigation();

  return (
    <motion.main initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.35 }} className="mx-auto w-full max-w-[1440px] space-y-5 p-4 sm:p-6 lg:p-8">
      <SearchHero onInvestigate={investigate} isLoading={loading} />
      <MockModeHint kind="ask" onPick={(query) => investigate(query)} />
      {loading && <LoadingTimeline />}
      {error && <ErrorCard error={error} />}
      {report && <AskResult data={report} onOpenPrescriptionCheck={onOpenPrescriptionCheck} />}
    </motion.main>
  );
}
