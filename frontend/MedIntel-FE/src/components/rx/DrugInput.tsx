import { ArrowRight, Pill, Plus, X } from "lucide-react";
import { ClipboardEvent, FormEvent, KeyboardEvent, useState } from "react";
import { Card } from "../Card";
import { Button } from "../ui/Button";

export const MAX_DRUGS = 5;

const examples: { label: string; drugs: string[] }[] = [
  { label: "Tizanidine + ciprofloxacin", drugs: ["tizanidine", "ciprofloxacin"] },
  { label: "Pantoprazole + clopidogrel", drugs: ["pantoprazole", "clopidogrel"] },
  { label: "Amoxicillin + levothyroxine", drugs: ["amoxicillin", "levothyroxine"] },
];

type DrugInputProps = {
  drugs: string[];
  onChange: (drugs: string[]) => void;
  onRun: (drugs: string[]) => void;
  isLoading: boolean;
};

// Same rule as the backend (Section 9.1): trim, drop empty, dedupe case-insensitive.
function addNames(current: string[], names: string[]) {
  const next = [...current];
  for (const name of names.map((n) => n.trim()).filter(Boolean)) {
    if (next.length >= MAX_DRUGS) break;
    if (!next.some((d) => d.toLowerCase() === name.toLowerCase())) next.push(name);
  }
  return next;
}

export function DrugInput({ drugs, onChange, onRun, isLoading }: DrugInputProps) {
  const [draft, setDraft] = useState("");
  const full = drugs.length >= MAX_DRUGS;

  function commitDraft() {
    if (!draft.trim()) return drugs;
    const next = addNames(drugs, draft.split(/[\n,]/));
    onChange(next);
    setDraft("");
    return next;
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && draft.trim()) {
      event.preventDefault();
      commitDraft();
    } else if (event.key === "Backspace" && !draft && drugs.length) {
      onChange(drugs.slice(0, -1));
    }
  }

  // One drug per line: a pasted list becomes one chip per line.
  function onPaste(event: ClipboardEvent<HTMLInputElement>) {
    const text = event.clipboardData.getData("text");
    if (/[\n\r]/.test(text)) {
      event.preventDefault();
      onChange(addNames(drugs, text.split(/[\r\n]+/)));
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = commitDraft();
    if (next.length) onRun(next);
  }

  return (
    <Card className="relative overflow-hidden p-6 sm:p-8">
      <div className="medical-grid pointer-events-none absolute inset-y-0 right-0 w-1/2 opacity-70" />
      <div className="relative">
        <h1 className="text-3xl font-bold tracking-normal text-emerald-950 dark:text-emerald-100 sm:text-4xl">Prescription Check</h1>
        <p className="mt-3 max-w-2xl text-base text-slate-600 dark:text-slate-300">
          Review up to {MAX_DRUGS} medications together against their FDA labels, for pharmacists and clinicians.
        </p>

        <form onSubmit={submit} className="mt-7 grid gap-4 xl:grid-cols-[1fr_220px]">
          <div className="flex min-h-14 flex-wrap items-center gap-2 rounded-lg border border-border bg-white px-3 py-2 shadow-card transition focus-within:border-emerald-400 focus-within:ring-4 focus-within:ring-emerald-600/10 dark:bg-slate-950">
            <Pill size={20} className="ml-1 shrink-0 text-emerald-700 dark:text-emerald-300" />
            {drugs.map((drug) => (
              <span key={drug.toLowerCase()} className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 py-1 pl-3 pr-1.5 text-sm font-medium text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300">
                {drug}
                <button
                  type="button"
                  onClick={() => onChange(drugs.filter((d) => d !== drug))}
                  className="rounded-full p-0.5 hover:bg-emerald-100 dark:hover:bg-emerald-900/60"
                  aria-label={`Remove ${drug}`}
                >
                  <X size={14} />
                </button>
              </span>
            ))}
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onKeyDown}
              onPaste={onPaste}
              onBlur={() => commitDraft()}
              disabled={full}
              placeholder={full ? `Maximum of ${MAX_DRUGS} medications` : drugs.length ? "Add another…" : "Type a medication and press Enter"}
              aria-label="Add a medication"
              className="h-10 min-w-[12rem] flex-1 bg-transparent px-1 text-base text-slate-950 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed dark:text-slate-100 dark:placeholder:text-slate-500"
            />
          </div>
          <Button type="submit" disabled={(drugs.length < 2 && !draft.trim()) || isLoading} className="h-14 text-base">
            Run check <ArrowRight size={20} />
          </Button>
        </form>

        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
          {drugs.length}/{MAX_DRUGS} added · press Enter after each name, or paste a list with one medication per line.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-3 text-sm">
          <span className="text-slate-600 dark:text-slate-300">Example checks:</span>
          {examples.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => {
                onChange(example.drugs);
                onRun(example.drugs);
              }}
              className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-white px-4 py-1.5 font-medium text-emerald-800 transition hover:bg-emerald-50 dark:border-emerald-900/60 dark:bg-slate-950 dark:text-emerald-300 dark:hover:bg-emerald-950/40"
            >
              <Plus size={14} />
              {example.label}
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}
