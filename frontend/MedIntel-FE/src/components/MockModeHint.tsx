import { FlaskConical } from "lucide-react";
import { useEffect, useState } from "react";

type MockModeHintProps = {
  kind: "ask" | "check";
  onPick: (value: string) => void;
};

// Dev-only list of the saved responses mock mode can serve. Renders nothing,
// and loads nothing, unless the dev server runs with VITE_USE_MOCKS=true.
export function MockModeHint(props: MockModeHintProps) {
  // Constant-false in production builds, so the hint is dropped from the bundle.
  if (!(import.meta.env.DEV && import.meta.env.VITE_USE_MOCKS === "true")) return null;
  return <MockModeList {...props} />;
}

function MockModeList({ kind, onPick }: MockModeHintProps) {
  const [items, setItems] = useState<string[]>([]);

  useEffect(() => {
    if (import.meta.env.DEV && import.meta.env.VITE_USE_MOCKS === "true") {
      import("../mocks").then((mocks) => {
        setItems(kind === "ask" ? mocks.savedQueries : mocks.savedDrugLists.map((drugs) => drugs.join(", ")));
      });
    }
  }, [kind]);


  if (!items.length) return null;

  return (
    <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50/50 p-4 text-sm dark:border-amber-800/70 dark:bg-amber-950/20">
      <div className="flex items-center gap-2 font-semibold text-amber-800 dark:text-amber-300">
        <FlaskConical size={16} />
        Mock mode: saved smoke-run responses, no backend calls
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => onPick(item)}
            className="rounded-full border border-amber-200 bg-white px-3 py-1 text-xs font-medium text-amber-900 transition hover:bg-amber-100 dark:border-amber-900/60 dark:bg-slate-950 dark:text-amber-200 dark:hover:bg-amber-950/50"
          >
            {item}
          </button>
        ))}
      </div>
    </div>
  );
}
