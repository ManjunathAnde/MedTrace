import { ChevronDown, ListChecks, Users } from "lucide-react";
import { useState } from "react";
import type { PrescriptionCheckResponse } from "../../api/types";
import { cn } from "../../lib/utils";
import { Card } from "../Card";
import { GapsBox } from "../evidence/GapsBox";
import { usePassagePanel } from "../evidence/PassagePanel";
import { StatusCard } from "../StatusCard";
import { InteractionCardView, NeedsReviewCard } from "./PairCards";
import { RecallsCard } from "./RecallsCard";
import { ResolutionTable } from "./ResolutionTable";

const FOOTER = "Class-level interactions were not checked.";

function NoDocumented({ pairs }: { pairs: [string, string][] }) {
  const [expanded, setExpanded] = useState(false);
  if (!pairs.length) return null;
  return (
    <Card className="p-0">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="flex w-full items-center justify-between gap-3 p-5 text-left font-semibold text-slate-800 dark:text-slate-200"
      >
        <span>No interaction documented in either FDA label ({pairs.length})</span>
        <ChevronDown size={18} className={cn("transition-transform", expanded && "rotate-180")} />
      </button>
      {expanded && (
        <ul className="space-y-1 border-t border-border px-5 py-4 text-sm text-slate-600 dark:text-slate-300">
          {pairs.map(([a, b]) => (
            <li key={`${a}+${b}`}>
              {a} + {b}: No interaction documented in either FDA label.
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Footer({ text }: { text: string }) {
  return <p className="px-1 text-sm font-medium text-slate-600 dark:text-slate-400">{text || FOOTER}</p>;
}

export function PrescriptionResult({ data }: { data: PrescriptionCheckResponse }) {
  const { panel, openPassage } = usePassagePanel();

  if (data.status !== "COMPLETE") {
    return (
      <div className="space-y-5">
        <StatusCard
          tone="slate"
          icon={data.status === "TOO_MANY" ? ListChecks : Users}
          eyebrow={data.status === "TOO_MANY" ? "Too many medications" : "Not enough medications"}
          title={data.status === "TOO_MANY" ? "Check up to 5 medications at once" : "Add another medication"}
          message={data.message}
        />
        <ResolutionTable resolution={data.resolution} />
        <Footer text={data.footer} />
      </div>
    );
  }

  const { meta } = data;
  return (
    <div className="space-y-5">
      <ResolutionTable resolution={data.resolution} />

      <section className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2 px-1">
          <h3 className="text-xl font-bold text-slate-950 dark:text-slate-50">Interactions</h3>
          <span className="text-sm text-slate-500 dark:text-slate-400">
            {meta.pairs_checked} {meta.pairs_checked === 1 ? "pair" : "pairs"} checked · {meta.pairs_with_candidates} mentioned in a label
          </span>
        </div>
        {data.interactions.map((card) => (
          <InteractionCardView key={card.pair.join("+")} card={card} evidence={data.evidence} onOpen={openPassage} />
        ))}
        {data.needs_review.map((review) => (
          <NeedsReviewCard key={review.pair.join("+")} review={review} evidence={data.evidence} onOpen={openPassage} />
        ))}
        {!data.interactions.length && !data.needs_review.length && (
          <Card className="p-5 text-sm text-slate-600 dark:text-slate-300">
            Neither FDA label names the other medication in its interaction, contraindication, boxed warning, or warning sections.
          </Card>
        )}
        <NoDocumented pairs={data.no_documented_interaction} />
      </section>

      <RecallsCard recalls={data.recalls} evidence={data.evidence} onOpen={openPassage} />
      <GapsBox gaps={data.gaps} title="Sources that could not be retrieved:" />
      <Footer text={data.footer} />
      {panel}
    </div>
  );
}
