import { motion } from "framer-motion";
import { ErrorCard } from "../components/ErrorCard";
import { LoadingTimeline } from "../components/LoadingTimeline";
import { ReportView } from "../components/report/ReportView";
import { SearchHero } from "../components/SearchHero";
import { useInvestigation } from "../hooks/useInvestigation";

export function InvestigatePage() {
  const { report, error, loading, investigate } = useInvestigation();

  return (
    <motion.main initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.35 }} className="mx-auto w-full max-w-[1440px] space-y-5 p-4 sm:p-6 lg:p-8">
      <SearchHero onInvestigate={investigate} isLoading={loading} />
      {loading && <LoadingTimeline />}
      {error && <ErrorCard error={error} />}
      {report && <ReportView data={report} />}
    </motion.main>
  );
}
