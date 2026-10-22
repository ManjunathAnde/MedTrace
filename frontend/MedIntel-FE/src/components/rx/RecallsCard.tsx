import { RotateCcw } from "lucide-react";
import type { EvidenceItem, PrescriptionCheckResponse } from "../../api/types";
import { Card } from "../Card";
import { SourceTag } from "../evidence/SourceTag";

type RecallsCardProps = {
  recalls: PrescriptionCheckResponse["recalls"];
  evidence: Record<string, EvidenceItem>;
  onOpen: (item: EvidenceItem, quote?: string) => void;
};

// The backend's recall template (Section 6) ends every record with this note;
// the card shows it once in the header instead. The source panel keeps the full text.
const RECALL_NOTE_SUFFIX = " Note: matched on ingredient name; confirm the specific product.";

function withoutRecallNote(text: string) {
  return text.endsWith(RECALL_NOTE_SUFFIX) ? text.slice(0, -RECALL_NOTE_SUFFIX.length) : text;
}

// Recalls per ingredient, shown directly from FDA enforcement records (Section 9.8).
export function RecallsCard({ recalls, evidence, onOpen }: RecallsCardProps) {
  if (!recalls.length) return null;
  const byIngredient = new Map<string, EvidenceItem[]>();
  for (const recall of recalls) {
    const item = evidence[recall.evidence_id];
    if (item) byIngredient.set(recall.ingredient, [...(byIngredient.get(recall.ingredient) ?? []), item]);
  }

  return (
    <Card className="p-5">
      <div className="mb-2 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
          <RotateCcw size={19} />
        </div>
        <h3 className="text-lg font-bold text-slate-950 dark:text-slate-50">Recalls</h3>
      </div>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">Matched on ingredient name; confirm the specific product.</p>
      <div className="space-y-4">
        {[...byIngredient.entries()].map(([ingredient, items]) => (
          <div key={ingredient}>
            <h4 className="mb-2 text-sm font-semibold capitalize text-slate-800 dark:text-slate-200">{ingredient}</h4>
            <ul className="space-y-2">
              {items.map((item) => (
                <li
                  key={item.id}
                  className={item.source === "absence"
                    ? "rounded-lg border border-dashed border-border p-3 text-sm text-slate-500 dark:text-slate-400"
                    : "rounded-lg border border-border bg-slate-50/40 p-3 text-sm leading-6 text-slate-700 dark:bg-slate-900/50 dark:text-slate-300"}
                >
                  <p>{withoutRecallNote(item.text)}</p>
                  <div className="mt-2">
                    <SourceTag item={item} onOpen={onOpen} />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
}
