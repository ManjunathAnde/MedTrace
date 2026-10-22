import type { EvidenceItem, Severity, Verdict } from "../../api/types";

// Display names for evidence sections (backend/evidence/store.py SECTION_HUMAN, plus FAERS and recalls).
const SECTION_NAMES: Record<string, string> = {
  boxed_warning: "Boxed warning",
  indications_and_usage: "Indications and usage",
  dosage_and_administration: "Dosage and administration",
  contraindications: "Contraindications",
  warnings: "Warnings",
  drug_interactions: "Drug interactions",
  faers: "Adverse event reports (FAERS)",
  faers_reaction: "Adverse event reports (FAERS)",
  faers_total: "Adverse event reports (FAERS)",
  recalls: "Recalls",
};

export function sectionName(section: string) {
  return SECTION_NAMES[section] ?? section.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function sourceName(item: EvidenceItem) {
  if (item.source === "dailymed_label") return "DailyMed";
  if (item.source === "faers") return "FAERS";
  if (item.source === "openfda_recall") return "FDA enforcement";
  if (item.section === "faers") return "FAERS";
  if (item.section === "recalls") return "FDA enforcement";
  return "DailyMed";
}

export const VERDICT_NAMES: Record<Verdict, string> = {
  CUT_QUOTE: "Quote not found in source",
  CUT_SUPPORT: "Not supported by the passage",
  CUT_DIRECTIVE: "Gave an instruction",
  CUT_BAD_ID: "Cited an unknown source",
};

export const SEVERITY_STYLES: Record<Severity, { badge: string; border: string; label: string }> = {
  High: {
    badge: "bg-red-600 text-white dark:bg-red-500 dark:text-red-950",
    border: "border-l-red-600 dark:border-l-red-500",
    label: "High",
  },
  Moderate: {
    badge: "bg-amber-500 text-amber-950 dark:bg-amber-400",
    border: "border-l-amber-500 dark:border-l-amber-400",
    label: "Moderate",
  },
  Info: {
    badge: "bg-sky-600 text-white dark:bg-sky-400 dark:text-sky-950",
    border: "border-l-sky-600 dark:border-l-sky-400",
    label: "Info",
  },
};

export function formatDate(value: string | null | undefined) {
  if (!value) return "date not listed";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}
