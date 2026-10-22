import { motion } from "framer-motion";
import { BadgeCheck, ExternalLink, Pill, ShieldCheck, ShieldPlus } from "lucide-react";
import type { InvestigateResponse, ResponseClaim } from "../../api/types";
import { Card } from "../Card";
import { GapsBox } from "../evidence/GapsBox";
import { formatDate, sectionName } from "../evidence/labels";
import { usePassagePanel } from "../evidence/PassagePanel";
import { RemovedClaims } from "../evidence/RemovedClaims";
import { SourceTag } from "../evidence/SourceTag";

// Claims grouped by section, sections in first-claim order (Section 11 item 4).
function groupBySection(claims: ResponseClaim[]) {
  const groups = new Map<string, ResponseClaim[]>();
  for (const claim of claims) {
    groups.set(claim.section, [...(groups.get(claim.section) ?? []), claim]);
  }
  return [...groups.entries()];
}

function Detail({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex items-start justify-between gap-4 text-sm">
      <span className="text-slate-500 dark:text-slate-400">{label}</span>
      <span className="text-right font-medium text-slate-800 dark:text-slate-200">{value || "Not available"}</span>
    </div>
  );
}

export function AnswerView({ data }: { data: InvestigateResponse }) {
  const { panel, openPassage } = usePassagePanel();
  const drug = data.drug;
  const label = drug?.label;
  const partial = data.status === "PARTIAL";

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <Card className="overflow-hidden">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="border-b border-border p-6">
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-emerald-700 text-white dark:bg-emerald-500 dark:text-emerald-950">
              <Pill size={28} />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-3xl font-bold text-slate-950 dark:text-slate-50">{drug?.preferred_name ?? "Medication"}</h2>
                <span className={partial
                  ? "inline-flex items-center gap-1 rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                  : "inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"}
                >
                  <ShieldCheck size={14} />
                  {partial ? "Partial answer" : "Answered"}
                </span>
              </div>
              {label && (
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                  Source label:{" "}
                  <a href={label.url} target="_blank" rel="noreferrer" className="font-medium text-emerald-800 underline decoration-emerald-300 underline-offset-2 hover:text-emerald-950 dark:text-emerald-300 dark:decoration-emerald-700">
                    {label.title}
                    <ExternalLink size={13} className="ml-1 inline" />
                  </a>
                  , effective {formatDate(label.effective_date)}
                </p>
              )}
              <p className="mt-1 flex items-center gap-1.5 text-sm font-semibold text-slate-800 dark:text-slate-200">
                <BadgeCheck size={16} className="text-emerald-700 dark:text-emerald-300" />
                Claims verified: {data.claims_kept} of {data.claims_total}
              </p>
            </div>
          </div>
        </motion.div>

        <div className="space-y-5 p-5 sm:p-6">
          {groupBySection(data.claims).map(([section, claims], index) => (
            <motion.section
              key={section}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 + index * 0.06, duration: 0.25 }}
            >
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">{sectionName(section)}</h3>
              <ul className="space-y-3">
                {claims.map((claim, claimIndex) => (
                  <li key={`${claim.evidence_id}-${claimIndex}`} className="rounded-lg border border-border bg-slate-50/40 p-4 dark:bg-slate-900/50">
                    <p className="leading-7 text-slate-800 dark:text-slate-200">{claim.text}</p>
                    <div className="mt-2">
                      <SourceTag item={data.evidence[claim.evidence_id]} quote={claim.quote} onOpen={openPassage} />
                    </div>
                  </li>
                ))}
              </ul>
            </motion.section>
          ))}
          <GapsBox gaps={data.gaps} />
          <RemovedClaims removed={data.removed} evidence={data.evidence} onOpen={openPassage} />
        </div>
      </Card>

      <aside className="space-y-5">
        <Card className="p-5">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
              <ShieldPlus size={19} />
            </div>
            <h3 className="font-bold text-slate-950 dark:text-slate-50">Answer details</h3>
          </div>
          <div className="space-y-4">
            <Detail label="You asked about" value={drug?.input_name} />
            <Detail label="Ingredients" value={drug?.ingredients.join(", ")} />
            <Detail label="RxCUI" value={drug?.rxcui} />
            <Detail label="Question type" value={data.intent?.replace(/_/g, " ")} />
            <Detail label="Checked by" value={data.meta.verifier_provider ? `Citation verifier (${data.meta.verifier_provider})` : "Citation verifier"} />
            <Detail label="Response time" value={`${(data.meta.latency_ms / 1000).toFixed(1)} s${data.meta.cache_hit ? " (cached)" : ""}`} />
          </div>
        </Card>
        <Card className="bg-emerald-50/50 p-5 dark:bg-emerald-950/20">
          <div className="flex gap-3">
            <ShieldPlus className="mt-0.5 shrink-0 text-emerald-700 dark:text-emerald-300" size={20} />
            <p className="text-sm leading-6 text-slate-700 dark:text-slate-300">
              Every claim above was checked against the FDA passage it cites. Not a substitute for professional medical advice.
            </p>
          </div>
        </Card>
      </aside>
      {panel}
    </div>
  );
}
