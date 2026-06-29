import { AlertTriangle, CircleSlash, Link2, RotateCcw, ShieldAlert } from "lucide-react";
import { Card } from "../Card";
import { itemDescription, itemTitle, renderValue } from "./reportUtils";

const icons = {
  warnings: AlertTriangle,
  contraindications: CircleSlash,
  interactions: Link2,
  adverseEvents: ShieldAlert,
  recalls: RotateCcw,
};

type SectionListProps = {
  title: string;
  type: keyof typeof icons;
  items: unknown[];
  empty: string;
};

export function SectionList({ title, type, items, empty }: SectionListProps) {
  const Icon = icons[type];

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
          <Icon size={19} />
        </div>
        <h3 className="text-lg font-bold text-slate-950 dark:text-slate-50">{title}</h3>
      </div>

      {items.length ? (
        <div className="space-y-3">
          {items.map((item, index) => (
            <div key={`${title}-${index}`} className="rounded-lg border border-border bg-slate-50/40 p-4 dark:bg-slate-900/50">
              <div className="font-semibold text-slate-900 dark:text-slate-100">{itemTitle(item, `${title} ${index + 1}`)}</div>
              <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">{itemDescription(item)}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border bg-slate-50/50 p-8 text-center text-sm text-slate-500 dark:bg-slate-900/50 dark:text-slate-400">{empty}</div>
      )}

      {items.length === 1 && typeof items[0] === "object" && (
        <pre className="mt-4 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">{renderValue(items[0])}</pre>
      )}
    </Card>
  );
}
