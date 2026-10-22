import { motion } from "framer-motion";
import { ErrorCard } from "../components/ErrorCard";
import { LoadingTimeline } from "../components/LoadingTimeline";
import { MockModeHint } from "../components/MockModeHint";
import { DrugInput } from "../components/rx/DrugInput";
import { PrescriptionResult } from "../components/rx/PrescriptionResult";
import { usePrescriptionCheck } from "../hooks/usePrescriptionCheck";

const CHECK_STEPS = [
  { label: "Name Recognition", children: ["RxNorm"] },
  { label: "Label Retrieval", children: ["DailyMed", "OpenFDA labels", "FDA Recall"] },
  { label: "Pair Search" },
  { label: "Interaction Review & Citation Check" },
];

type PrescriptionCheckPageProps = {
  drugs: string[];
  onDrugsChange: (drugs: string[]) => void;
};

export function PrescriptionCheckPage({ drugs, onDrugsChange }: PrescriptionCheckPageProps) {
  const { result, error, loading, run } = usePrescriptionCheck();

  return (
    <motion.main initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.35 }} className="mx-auto w-full max-w-[1440px] space-y-5 p-4 sm:p-6 lg:p-8">
      <DrugInput drugs={drugs} onChange={onDrugsChange} onRun={run} isLoading={loading} />
      <MockModeHint
        kind="check"
        onPick={(list) => {
          const picked = list.split(", ");
          onDrugsChange(picked.slice(0, 5));
          run(picked);
        }}
      />
      {loading && <LoadingTimeline steps={CHECK_STEPS} title="Checking medications together" />}
      {error && <ErrorCard error={error} />}
      {result && <PrescriptionResult data={result} />}
    </motion.main>
  );
}
