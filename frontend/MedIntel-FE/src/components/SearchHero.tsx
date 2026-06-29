import { ArrowRight, CheckCircle2, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import { Card } from "./Card";
import { Button } from "./ui/Button";

const chips = ["Warfarin", "Metformin", "Ozempic", "Lisinopril", "Aspirin"];
const trustSources = ["RxNorm", "DailyMed", "FDA", "OpenFDA"];

type SearchHeroProps = {
  onInvestigate: (query: string) => void;
  isLoading: boolean;
};

export function SearchHero({ onInvestigate, isLoading }: SearchHeroProps) {
  const [query, setQuery] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    onInvestigate(query);
  }

  return (
    <Card className="relative overflow-hidden p-6 sm:p-8">
      <div className="medical-grid pointer-events-none absolute inset-y-0 right-0 w-1/2 opacity-70" />
      <div className="relative">
        <h1 className="text-3xl font-bold tracking-normal text-emerald-950 dark:text-emerald-100 sm:text-4xl">Investigate a Medication</h1>
        <p className="mt-3 max-w-2xl text-base text-slate-600 dark:text-slate-300">Get comprehensive, evidence-based insights from trusted healthcare sources.</p>

        <form onSubmit={submit} className="mt-7 grid gap-4 xl:grid-cols-[1fr_220px]">
          <label className="relative block">
            <Search className="absolute left-5 top-1/2 -translate-y-1/2 text-emerald-700 dark:text-emerald-300" size={22} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Investigate a medication..."
              className="h-14 w-full rounded-lg border border-border bg-white pl-14 pr-5 text-base text-slate-950 shadow-card outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:ring-4 focus:ring-emerald-600/10 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500"
            />
          </label>
          <Button type="submit" disabled={!query.trim() || isLoading} className="h-14 text-base">
            Investigate <ArrowRight size={20} />
          </Button>
        </form>

        <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span>Powered by</span>
          {trustSources.map((source) => (
            <span key={source} className="inline-flex items-center gap-1 rounded-full border border-emerald-100 bg-white/70 px-2.5 py-1 font-medium text-slate-600 dark:border-emerald-900/50 dark:bg-slate-950/70 dark:text-slate-300">
              <CheckCircle2 size={13} className="text-emerald-700 dark:text-emerald-300" />
              {source}
            </span>
          ))}
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3 text-sm">
          <span className="text-slate-600 dark:text-slate-300">Popular searches:</span>
          {chips.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => {
                setQuery(chip);
                onInvestigate(chip);
              }}
              className="rounded-full border border-emerald-200 bg-white px-4 py-1.5 font-medium text-emerald-800 transition hover:bg-emerald-50 dark:border-emerald-900/60 dark:bg-slate-950 dark:text-emerald-300 dark:hover:bg-emerald-950/40"
            >
              {chip}
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}
