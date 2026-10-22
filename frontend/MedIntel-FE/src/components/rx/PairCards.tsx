import { CircleHelp, Link2 } from "lucide-react";
import type { EvidenceItem, InteractionCard, NeedsReview } from "../../api/types";
import { cn } from "../../lib/utils";
import { Card } from "../Card";
import { SEVERITY_STYLES } from "../evidence/labels";
import { RemovedClaims } from "../evidence/RemovedClaims";
import { SourceTag } from "../evidence/SourceTag";

type OnOpen = (item: EvidenceItem, quote?: string) => void;

const FINDING_TEXT = {
  INTERACTION_DOCUMENTED: "Interaction documented in an FDA label",
  NO_INTERACTION_STATED: "Label states no clinically significant interaction",
};

function PairTitle({ pair }: { pair: [string, string] }) {
  return (
    <h4 className="text-lg font-bold text-slate-950 dark:text-slate-50">
      {pair[0]} <span className="text-slate-400">+</span> {pair[1]}
    </h4>
  );
}

// Interaction card: pair, severity badge, the rule that fired, verified claims with source tags.
export function InteractionCardView({ card, evidence, onOpen }: { card: InteractionCard; evidence: Record<string, EvidenceItem>; onOpen: OnOpen }) {
  const style = SEVERITY_STYLES[card.severity];
  return (
    <Card className={cn("border-l-4 p-5", style.border)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <PairTitle pair={card.pair} />
          <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">{FINDING_TEXT[card.finding]}</p>
        </div>
        <span className={cn("rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[0.12em]", style.badge)}>
          {style.label} severity
        </span>
      </div>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        Rule: <span className="font-medium text-slate-700 dark:text-slate-300">{card.severity_rule}</span>
      </p>
      <ul className="mt-4 space-y-3">
        {card.claims.map((claim, index) => (
          <li key={`${claim.evidence_id}-${index}`} className="rounded-lg border border-border bg-slate-50/40 p-4 dark:bg-slate-900/50">
            <p className="leading-7 text-slate-800 dark:text-slate-200">{claim.text}</p>
            <div className="mt-2">
              <SourceTag item={evidence[claim.evidence_id]} quote={claim.quote} showProduct onOpen={onOpen} />
            </div>
          </li>
        ))}
      </ul>
      {card.removed.length > 0 && (
        <div className="mt-4">
          <RemovedClaims removed={card.removed} evidence={evidence} onOpen={onOpen} />
        </div>
      )}
    </Card>
  );
}

// Needs review: the label mentions the other drug, but nothing could be verified.
export function NeedsReviewCard({ review, evidence, onOpen }: { review: NeedsReview; evidence: Record<string, EvidenceItem>; onOpen: OnOpen }) {
  return (
    <Card className="border-l-4 border-l-slate-400 p-5 dark:border-l-slate-500">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <PairTitle pair={review.pair} />
          <p className="mt-0.5 flex items-center gap-1.5 text-sm text-slate-600 dark:text-slate-300">
            <CircleHelp size={15} />
            {review.reason}
          </p>
        </div>
        <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-bold uppercase tracking-[0.12em] text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          Needs review
        </span>
      </div>
      <div className="mt-4">
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
          <Link2 size={13} /> Matched passages ({review.evidence_ids.length})
        </p>
        <div className="flex flex-wrap gap-2">
          {review.evidence_ids.map((id) => (
            <SourceTag key={id} item={evidence[id]} showProduct onOpen={onOpen} />
          ))}
        </div>
      </div>
      {review.removed.length > 0 && (
        <div className="mt-4">
          <RemovedClaims removed={review.removed} evidence={evidence} onOpen={onOpen} />
        </div>
      )}
    </Card>
  );
}
