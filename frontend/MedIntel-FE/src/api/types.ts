// v2 response shapes (PROJECT.md Section 10), mirroring backend/models/report.py.

export type Provider = "gemini" | "groq";

export type EvidenceSource = "dailymed_label" | "openfda_recall" | "faers" | "absence";

export type EvidenceItem = {
  id: string;
  internal_id: string;
  product: string;
  ingredient: string | null;
  rxcui: string;
  source: EvidenceSource;
  section: string;
  text: string;
  url: string;
  label_title: string | null;
  label_set_id: string | null;
  label_effective_date: string | null;
  retrieved_at: string;
};

export type LabelRef = {
  title: string;
  set_id: string;
  effective_date: string | null;
  url: string;
};

export type ResponseClaim = {
  text: string;
  section: string;
  evidence_id: string;
  quote: string;
};

export type Verdict = "CUT_QUOTE" | "CUT_SUPPORT" | "CUT_DIRECTIVE" | "CUT_BAD_ID";

export type RemovedClaim = {
  text: string;
  evidence_id: string;
  quote: string;
  verdict: Verdict;
  reason: string;
};

// --- POST /investigate ---

export type InvestigateStatus =
  | "ANSWERED"
  | "PARTIAL"
  | "INSUFFICIENT_EVIDENCE"
  | "UNAVAILABLE"
  | "BLOCKED"
  | "NO_DRUG"
  | "NOT_RECOGNIZED"
  | "ONE_AT_A_TIME"
  | "REDIRECT";

export type InvestigateResponse = {
  version: "v2";
  status: InvestigateStatus;
  message: string | null;
  block_type: "PERSONAL_ADVICE" | "SELF_HARM_RISK" | null;
  redirect: { to: string; drugs: string[] } | null;
  intent: string | null;
  drug: {
    input_name: string;
    rxcui: string | null;
    preferred_name: string;
    ingredients: string[];
    label: LabelRef | null;
  } | null;
  claims: ResponseClaim[];
  claims_total: number;
  claims_kept: number;
  removed: RemovedClaim[];
  gaps: string[];
  evidence: Record<string, EvidenceItem>;
  meta: {
    latency_ms: number;
    llm_calls: number;
    verifier_provider: Provider | null;
    cache_hit: boolean;
    verified: boolean;
    synthesizer_provider: Provider | null;
  };
};

// --- POST /prescription-check ---

export type Severity = "High" | "Moderate" | "Info";

export type Resolution = {
  input_name: string;
  status: "RESOLVED" | "NOT_RECOGNIZED";
  rxcui: string | null;
  preferred_name: string | null;
  ingredients: string[];
  label: LabelRef | null;
  message: string | null;
};

export type InteractionCard = {
  pair: [string, string];
  finding: "INTERACTION_DOCUMENTED" | "NO_INTERACTION_STATED";
  severity: Severity;
  severity_rule: string;
  claims: ResponseClaim[];
  removed: RemovedClaim[];
};

export type NeedsReview = {
  pair: [string, string];
  evidence_ids: string[];
  reason: string;
  removed: RemovedClaim[];
};

export type PrescriptionCheckResponse = {
  version: "v2";
  status: "COMPLETE" | "TOO_FEW" | "TOO_MANY";
  message: string | null;
  resolution: Resolution[];
  interactions: InteractionCard[];
  needs_review: NeedsReview[];
  no_documented_interaction: [string, string][];
  recalls: { ingredient: string; evidence_id: string }[];
  gaps: string[];
  evidence: Record<string, EvidenceItem>;
  footer: string;
  meta: {
    latency_ms: number;
    llm_calls: number;
    pairs_checked: number;
    pairs_with_candidates: number;
    verifier_provider: Provider | null;
    cache_hit: boolean;
    verified: boolean;
  };
};
