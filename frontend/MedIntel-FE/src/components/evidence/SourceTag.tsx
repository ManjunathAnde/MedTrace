import { FileSearch } from "lucide-react";
import type { EvidenceItem } from "../../api/types";
import { sectionName, sourceName } from "./labels";

type SourceTagProps = {
  item: EvidenceItem | undefined;
  quote?: string;
  showProduct?: boolean;
  onOpen: (item: EvidenceItem, quote?: string) => void;
};

// `[DailyMed · Boxed warning]` — one click opens the full passage (Section 11).
export function SourceTag({ item, quote, showProduct = false, onOpen }: SourceTagProps) {
  if (!item) return null;
  const parts = [sourceName(item), ...(showProduct ? [item.product] : []), sectionName(item.section)];

  return (
    <button
      type="button"
      onClick={() => onOpen(item, quote)}
      className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50/60 px-2 py-0.5 text-xs font-medium text-emerald-800 transition hover:bg-emerald-100 focus:outline-none focus:ring-2 focus:ring-emerald-600/25 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300 dark:hover:bg-emerald-950/60"
      aria-label={`Open source passage ${item.id}: ${parts.join(", ")}`}
    >
      <FileSearch size={13} className="shrink-0" />
      <span className="truncate">[{parts.join(" · ")}]</span>
    </button>
  );
}
