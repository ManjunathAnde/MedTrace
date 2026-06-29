import { motion } from "framer-motion";
import { Check, Circle } from "lucide-react";
import { useEffect, useState } from "react";
import { Card } from "./Card";

const steps = [
  { label: "Safety Check" },
  { label: "Medication Recognition" },
  { label: "Intent Classification" },
  {
    label: "Evidence Collection",
    children: ["RxNorm", "DailyMed", "FDA Recall", "OpenFDA FAERS"],
  },
  { label: "AI Report Generation", pending: true },
];

const STAGE_INTERVAL_MS = 500;
const FINAL_STAGE_INDEX = steps.length - 1;

export function LoadingTimeline() {
  const [activeStage, setActiveStage] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveStage((stage) => Math.min(stage + 1, FINAL_STAGE_INDEX));
    }, STAGE_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, []);

  return (
    <Card className="p-6 sm:p-8">
      <div className="mb-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-300">Investigation running</p>
        <h2 className="mt-2 text-2xl font-bold text-slate-950 dark:text-slate-50">Collecting medication intelligence</h2>
      </div>
      <div className="space-y-3">
        {steps.map((step, index) => {
          const isComplete = index < activeStage;
          const isActive = index === activeStage;
          const isWaiting = index > activeStage;

          return (
          <motion.div
            key={step.label}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: isWaiting ? 0.55 : 1, x: 0 }}
            transition={{ duration: 0.28 }}
            className="rounded-lg border border-emerald-100 bg-emerald-50/40 p-4 dark:border-emerald-900/50 dark:bg-emerald-950/20"
          >
            <div className="flex items-center gap-3">
              <motion.span
                animate={isActive ? { scale: [1, 1.08, 1], opacity: [0.65, 1, 0.65] } : { scale: 1 }}
                transition={{ repeat: isActive ? Infinity : 0, duration: 1.6 }}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-emerald-700 dark:bg-slate-950 dark:text-emerald-300"
              >
                {isComplete ? <Check size={17} /> : <Circle size={14} fill="currentColor" />}
              </motion.span>
              <span className="font-medium text-slate-700 dark:text-slate-200">{step.label}</span>
            </div>
            {step.children && (isActive || isComplete) && (
              <div className="ml-11 mt-3 grid gap-2 sm:grid-cols-2">
                {step.children.map((child, childIndex) => (
                  <motion.div
                    key={child}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.22 + childIndex * 0.12, duration: 0.25 }}
                    className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300"
                  >
                    <Check size={15} className="text-emerald-700 dark:text-emerald-300" />
                    {child}
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
          );
        })}
      </div>
    </Card>
  );
}
