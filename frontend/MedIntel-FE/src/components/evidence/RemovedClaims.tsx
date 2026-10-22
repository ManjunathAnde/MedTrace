import { ChevronDown, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { EvidenceItem, RemovedClaim } from "../../api/types";
import { cn } from "../../lib/utils";
import { VERDICT_NAMES } from "./labels";
import { SourceTag } from "./SourceTag";

type RemovedClaimsProps = {
  removed: RemovedClaim[];
  evidence: Record<string, EvidenceItem>;
  onOpen: (item: EvidenceItem, quote?: string) => void;
};

// "Removed by verifier (N)", collapsed: the verifier's work made visible (Section 11).
export function RemovedClaims({ removed, evidence, onOpen }: RemovedClaimsProps) {
  const [expanded, setExpanded] = useState(false);
  if (!removed.length) return null;

  return (
    <div className="rounded-lg border border-border bg-slate-50/50 dark:bg-slate-900/40">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold text-slate-700 dark:text-slate-300"
      >
        <span className="flex items-center gap-2">
          <ShieldCheck size={16} className="text-slate-500 dark:text-slate-400" />
          Removed by verifier ({removed.length})
        </span>
        <ChevronDown size={16} className={cn("transition-transform", expanded && "rotate-180")} />
      </button>
      {expanded && (
        <ul className="space-y-3 border-t border-border px-4 py-3">
          {removed.map((claim, index) => (
            <li key={`${claim.evidence_id}-${index}`} className="text-sm leading-6">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  {VERDICT_NAMES[claim.verdict]}
                </span>
                <code className="text-xs text-slate-500 dark:text-slate-400">{claim.verdict}</code>
                <SourceTag item={evidence[claim.evidence_id]} quote={claim.quote} onOpen={onOpen} />
              </div>
              <p className="mt-1 text-slate-500 line-through decoration-slate-400/70 dark:text-slate-400">{claim.text}</p>
              <p className="text-slate-600 dark:text-slate-300">
                <span className="font-medium">Why: </span>
                {claim.reason}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
