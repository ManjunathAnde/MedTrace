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
];

const STAGE_INTERVAL_MS = 500;
const REPORT_GENERATION_STAGE = steps.length;

const facts = [
  "The FDA's Adverse Event Reporting System now updates in real time with over 31 million reports, making it one of the largest drug safety databases in the world.",
  "Adverse events are significantly underreported to the FDA — the average reporting rate is just around 6%, which is why FAERS data should be read as a signal, not a complete picture.",
  "About 75% of adverse event reports in FAERS come from drug manufacturers, who are legally required to forward reports they receive from doctors and patients.",
  "FDA drug recalls are classified into three tiers — Class I (reasonable chance of serious harm), Class II (temporary or reversible harm), and Class III (unlikely to cause harm) — based purely on risk severity.",
];

const FACT_TYPE_DURATION_MS = 5000;
const FACT_HOLD_MS = 7000;

function RotatingFactDisplay() {
  const [factIndex, setFactIndex] = useState(0);
  const [visibleText, setVisibleText] = useState("");

  useEffect(() => {
    const fact = facts[factIndex];
    const charDelay = FACT_TYPE_DURATION_MS / fact.length;
    let charIndex = 0;
    let typeTimer: number | undefined;
    let holdTimer: number | undefined;
    let isMounted = true;

    setVisibleText("");

    const typeNext = () => {
      if (!isMounted) return;
      charIndex += 1;
      setVisibleText(fact.slice(0, charIndex));

      if (charIndex < fact.length) {
        typeTimer = window.setTimeout(typeNext, charDelay);
        return;
      }

      holdTimer = window.setTimeout(() => {
        if (isMounted) setFactIndex((index) => (index + 1) % facts.length);
      }, FACT_HOLD_MS);
    };

    typeTimer = window.setTimeout(typeNext, charDelay);

    return () => {
      isMounted = false;
      if (typeTimer !== undefined) window.clearTimeout(typeTimer);
      if (holdTimer !== undefined) window.clearTimeout(holdTimer);
    };
  }, [factIndex]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      className="mt-5 min-h-40 rounded-lg border border-emerald-100 bg-white/70 p-4 dark:border-emerald-900/50 dark:bg-slate-950/50"
      aria-live="polite"
    >
      <p className="text-sm font-semibold uppercase tracking-[0.16em] text-emerald-700 dark:text-emerald-300">AI report generation</p>
      <p className="mt-3 text-base leading-7 text-slate-700 dark:text-slate-200">{visibleText}</p>
    </motion.div>
  );
}

export function LoadingTimeline() {
  const [activeStage, setActiveStage] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveStage((stage) => Math.min(stage + 1, REPORT_GENERATION_STAGE));
    }, STAGE_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, []);

  return (
    <Card className="p-5 sm:p-6">
      <div className="mb-4">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-300">Investigation running</p>
        <h2 className="mt-2 text-2xl font-bold text-slate-950 dark:text-slate-50">Collecting medication intelligence</h2>
      </div>
      <div className="space-y-2">
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
            className="rounded-lg border border-emerald-100 bg-emerald-50/40 p-3 dark:border-emerald-900/50 dark:bg-emerald-950/20"
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
              <div className="ml-11 mt-2 grid gap-1.5 sm:grid-cols-2">
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
      {activeStage >= REPORT_GENERATION_STAGE && <RotatingFactDisplay />}
    </Card>
  );
}
