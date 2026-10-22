import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { EvidenceItem } from "../../api/types";
import { Button } from "../ui/Button";
import { findQuote } from "./highlight";
import { formatDate, sectionName, sourceName } from "./labels";

type Open = { item: EvidenceItem; quote?: string } | null;

function Passage({ text, quote }: { text: string; quote?: string }) {
  const span = quote ? findQuote(text, quote) : null;
  if (!span) return <>{text}</>;
  return (
    <>
      {text.slice(0, span[0])}
      <mark className="rounded bg-amber-200 px-0.5 text-slate-950 dark:bg-amber-400/80">{text.slice(span[0], span[1])}</mark>
      {text.slice(span[1])}
    </>
  );
}

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 text-sm">
      <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="break-words font-medium text-slate-800 dark:text-slate-200">{value}</dd>
    </div>
  );
}

function PassagePanel({ open, onClose }: { open: Open; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Source passage">
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-slate-950/30"
            onClick={onClose}
            aria-label="Close source passage"
          />
          <motion.aside
            initial={{ x: 40, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 40, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute right-0 top-0 flex h-full w-full max-w-xl flex-col border-l border-border bg-white shadow-soft dark:bg-slate-950"
          >
            <div className="flex items-start justify-between gap-4 border-b border-border p-5">
              <div className="min-w-0">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700 dark:text-emerald-300">
                  {sourceName(open.item)} · {open.item.id}
                </div>
                <h3 className="mt-1 text-lg font-bold text-slate-950 dark:text-slate-50">
                  {sectionName(open.item.section)} — {open.item.product}
                </h3>
              </div>
              <Button variant="ghost" className="h-9 w-9 shrink-0 px-0" onClick={onClose} aria-label="Close source passage">
                <X size={18} />
              </Button>
            </div>
            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              <p className="whitespace-pre-line text-[15px] leading-7 text-slate-800 dark:text-slate-200">
                <Passage text={open.item.text} quote={open.quote} />
              </p>
              {open.quote && !findQuote(open.item.text, open.quote) && (
                <p className="rounded-lg border border-dashed border-border p-3 text-sm text-slate-500 dark:text-slate-400">
                  Quote: “{open.quote}”
                </p>
              )}
              <dl className="space-y-2 rounded-lg border border-border bg-slate-50/60 p-4 dark:bg-slate-900/50">
                <Detail label="Label" value={open.item.label_title} />
                <Detail label="Set ID" value={open.item.label_set_id} />
                <Detail label="Effective" value={open.item.label_effective_date ? formatDate(open.item.label_effective_date) : null} />
                <Detail label="Ingredient" value={open.item.ingredient} />
                <Detail label="Retrieved" value={formatDate(open.item.retrieved_at)} />
              </dl>
            </div>
            <div className="border-t border-border p-5">
              <a
                href={open.item.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-emerald-200 bg-white px-4 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-600/25 dark:border-emerald-900/70 dark:bg-slate-950 dark:text-emerald-300 dark:hover:bg-emerald-950/40"
              >
                Open in {sourceName(open.item)} <ExternalLink size={16} />
              </a>
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
}

// One panel per results view; `openPassage` is passed to every SourceTag.
export function usePassagePanel() {
  const [open, setOpen] = useState<Open>(null);
  const close = useCallback(() => setOpen(null), []);
  const openPassage = useCallback((item: EvidenceItem, quote?: string) => setOpen({ item, quote }), []);
  return { panel: <PassagePanel open={open} onClose={close} />, openPassage };
}
