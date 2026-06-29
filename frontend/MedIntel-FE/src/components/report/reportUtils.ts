import { asArray, pickNumber, pickString, titleCase } from "../../lib/utils";
import { InvestigationResponse } from "../../hooks/useInvestigation";

export const SYNTHESIS_UNAVAILABLE_SUMMARY = "Report generation temporarily unavailable";

export type ReportSectionKey =
  | "summary"
  | "warnings"
  | "contraindications"
  | "interactions"
  | "adverseEvents"
  | "recalls"
  | "sources";

export type ReportViewModel = {
  raw: InvestigationResponse;
  drugName: string;
  profileUsed: string;
  completenessScore: string;
  duration?: string;
  summary: string;
  keyFindings: unknown[];
  warnings: unknown[];
  contraindications: unknown[];
  interactions: unknown[];
  adverseEvents: unknown[];
  recalls: unknown[];
  sources: unknown[];
  limitations: unknown[];
  isSynthesisUnavailable: boolean;
  completenessValue?: number;
};

function sectionArray(data: InvestigationResponse, keys: string[]) {
  for (const key of keys) {
    const value = data[key];
    const array = asArray(value);
    if (array.length) return array;
  }
  return [];
}

function nestedString(data: InvestigationResponse, key: string, nestedKeys: string[]) {
  const value = data[key];
  if (value && typeof value === "object") return pickString(value, nestedKeys, "");
  return "";
}

function formatCompletenessScore(score?: number, fallback = "Not provided") {
  if (score === undefined) return fallback;
  return score <= 1 ? `${Math.round(score * 100)}%` : `${score}%`;
}

function limitationContradictsCompleteRetrieval(limitation: unknown) {
  const text = renderValue(limitation).toLowerCase();
  return text.includes("source") && text.includes("unavailable");
}

export function createReportView(data: InvestigationResponse): ReportViewModel {
  const duration = pickString(data, ["investigation_duration", "investigationDuration", "duration", "elapsed_time"], "");
  const score = pickNumber(data, ["completeness_score", "completenessScore", "score"]);

  const warnings = sectionArray(data, ["warnings", "safety_warnings", "safetyWarnings"]);
  const contraindications = sectionArray(data, ["contraindications"]);
  const interactions = sectionArray(data, ["interactions", "drug_interactions", "drugInteractions"]);
  const adverseEvents = sectionArray(data, ["adverse_events", "adverseEvents", "events"]);
  const recalls = sectionArray(data, ["recalls", "fda_recalls", "fdaRecalls"]);
  const sources = sectionArray(data, ["sources_used", "sourcesUsed", "sources", "data_sources", "dataSources"]);
  const rawLimitations = sectionArray(data, ["limitations", "limits", "caveats"]);
  const limitations = score === 1 ? rawLimitations.filter((item) => !limitationContradictsCompleteRetrieval(item)) : rawLimitations;
  const summary = pickString(data, ["summary", "ai_summary", "aiSummary", "risk_summary"], nestedString(data, "report", ["summary", "ai_summary"]) || "No narrative summary was returned by the API.");

  return {
    raw: data,
    drugName: pickString(data, ["drug_name", "drugName", "medication", "name", "query"], "Medication"),
    profileUsed: titleCase(pickString(data, ["profile_used", "profileUsed", "profile"], "Full Investigation")),
    completenessScore: formatCompletenessScore(score, pickString(data, ["completeness_score", "completenessScore"], "Not provided")),
    duration: duration || undefined,
    summary,
    keyFindings: sectionArray(data, ["key_findings", "keyFindings", "findings"]),
    warnings,
    contraindications,
    interactions,
    adverseEvents,
    recalls,
    sources,
    limitations,
    isSynthesisUnavailable: summary === SYNTHESIS_UNAVAILABLE_SUMMARY,
    completenessValue: score,
  };
}

export function renderValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not available";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map(renderValue).join(", ");
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    return Object.entries(record)
      .map(([key, entry]) => `${titleCase(key)}: ${renderValue(entry)}`)
      .join(" • ");
  }
  return "Not available";
}

export function itemTitle(item: unknown, fallback: string) {
  return pickString(item, ["title", "name", "label", "drug", "source", "description"], fallback);
}

export function itemDescription(item: unknown) {
  if (typeof item === "string") return item;
  return pickString(item, ["description", "details", "text", "message", "summary", "effect"], renderValue(item));
}
