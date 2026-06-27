"""
Gemini Risk Analyst.

Receives MedicationEvidence (structured API data) and returns MedicationReport
(structured Gemini analysis). Gemini fills the 8 analytical fields only; Python
assembles the final report by copying the 4 metadata fields directly from evidence
so that profile_used, drug_name, completeness_score, and sources_used are always
ground-truth values, never Gemini estimates.

Fails safe on all API errors, network failures, and response validation failures —
returning a minimal report so Gemini unavailability never raises to the caller.
"""

import os

from google import genai
from google.genai import errors as genai_errors, types
from pydantic import ValidationError

from backend.models.base import BaseSchema
from backend.models.enums import ProfileType
from backend.models.evidence import MedicationEvidence
from backend.models.report import MedicationReport

_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

_PROFILE_INSTRUCTIONS: dict[ProfileType, str] = {
    ProfileType.FULL_INVESTIGATION: """\
Populate all sections:
  summary           — one paragraph medication overview (name, class, key uses)
  key_findings      — 3-7 most critical safety findings, prioritized by severity
  warnings          — boxed warnings and major precautions from label evidence
  contraindications — absolute and relative contraindications from label evidence
  recalls           — one entry per recall record (reason, classification, date, status)
  adverse_events    — top reported events from FAERS, ranked by frequency
  interactions      — drug interactions from label evidence, noting severity where available
  limitations       — one entry per failed or unavailable source; note completeness score""",

    ProfileType.WARNINGS_REVIEW: """\
Populate:
  summary      — one paragraph overview focused on the medication's safety profile
  key_findings — most critical warning-related findings
  warnings     — boxed warnings and major precautions from label evidence
  limitations  — include one entry for each failed or unavailable source, and add:
                 "This report covers documented warnings only. Recall history, adverse
                 events, and interactions were not analyzed for this request."

Leave empty ([]): contraindications, recalls, adverse_events, interactions""",

    ProfileType.CONTRAINDICATIONS_REVIEW: """\
Populate:
  summary           — one paragraph overview focused on who the medication is unsuitable for
  key_findings      — most important contraindication findings
  contraindications — absolute and relative contraindications from label evidence
  limitations       — include one entry for each failed or unavailable source, and add:
                      "This report covers documented contraindications only. Warnings,
                      recall history, adverse events, and interactions were not analyzed
                      for this request."

Leave empty ([]): warnings, recalls, adverse_events, interactions""",

    ProfileType.RECALL_INVESTIGATION: """\
Populate:
  summary      — current recall status summary for this medication
  key_findings — most significant recall findings
  recalls      — one entry per recall record; include reason, FDA classification, date, status
  limitations  — include one entry for each failed or unavailable source, and add:
                 "This report covers FDA recall records only. Drug label warnings,
                 adverse events, and interactions were not analyzed for this request."

Leave empty ([]): warnings, contraindications, adverse_events, interactions""",

    ProfileType.INTERACTION_INVESTIGATION: """\
Populate:
  summary      — one paragraph overview of the medication's interaction profile
  key_findings — most significant interaction findings
  interactions — all interactions from label evidence; note severity where available
  limitations  — include one entry for each failed or unavailable source, and add:
                 "This report covers documented drug interactions only. Recall history,
                 adverse events, and warnings were not analyzed for this request."

Leave empty ([]): warnings, contraindications, recalls, adverse_events""",

    ProfileType.ADVERSE_EVENT_INVESTIGATION: """\
Populate:
  summary        — one paragraph overview of the adverse event reporting landscape
  key_findings   — most significant adverse event signals
  adverse_events — top reported events from FAERS ranked by frequency; each entry
                   must include: "Reports reflect FDA FAERS submissions and do not
                   establish causation."
  limitations    — include one entry for each failed or unavailable source, and add:
                   "This report covers FDA adverse event reports only. Drug label
                   warnings, recall history, and interactions were not analyzed for
                   this request."

Leave empty ([]): warnings, contraindications, recalls, interactions""",
}

_PROMPT_TEMPLATE = """\
You are a medication intelligence analyst.

Evidence has been collected from authoritative healthcare APIs: RxNorm (drug
identity), DailyMed/OpenFDA (prescribing label), FDA Recall Database
(regulatory actions), and OpenFDA FAERS (adverse event reports).

CRITICAL RULES
1. Every factual claim must be directly supported by the provided evidence.
   Do not use prior knowledge, medical training, or information not present
   in the evidence package.
2. If an evidence field is null or an evidence section is absent, return an
   empty list [] for the corresponding report field. Do not substitute general
   medical knowledge.
3. Any entry in adverse_events must include the statement:
   "These reports reflect FDA FAERS submissions and do not establish causation."
4. Populate only the sections specified for this retrieval profile.
   All other list fields must be returned as empty lists [].

RETRIEVAL PROFILE: {profile_name}

{profile_instructions}

EVIDENCE PACKAGE (JSON)
-----------------------
{evidence_json}
-----------------------

Produce the report now. Every claim must be traceable to the evidence above.
"""


class _GeminiReportContent(BaseSchema):
    """Private schema for Gemini structured output.

    Covers only the 8 analytical fields. The 4 metadata fields (profile_used,
    drug_name, completeness_score, sources_used) are copied from evidence in
    Python — Gemini never sets them."""

    summary: str
    key_findings: list[str]
    warnings: list[str]
    contraindications: list[str]
    recalls: list[str]
    adverse_events: list[str]
    interactions: list[str]
    limitations: list[str]


def _fail_safe(evidence: MedicationEvidence) -> MedicationReport:
    return MedicationReport(
        profile_used=evidence.profile_used,
        drug_name=evidence.drug_identity.input_name,
        summary="Report generation temporarily unavailable",
        key_findings=[],
        warnings=[],
        contraindications=[],
        recalls=[],
        adverse_events=[],
        interactions=[],
        limitations=[],
        sources_used=evidence.metadata.successful_sources,
        completeness_score=evidence.metadata.completeness_score,
    )


async def generate_report(evidence: MedicationEvidence) -> MedicationReport:
    """
    Analyze structured medication evidence and return a MedicationReport.

    Catches only expected runtime failures (API errors, network errors,
    response validation errors). Programming errors propagate normally.
    """
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    prompt = _PROMPT_TEMPLATE.format(
        profile_name=evidence.profile_used.value,
        profile_instructions=_PROFILE_INSTRUCTIONS[evidence.profile_used],
        evidence_json=evidence.model_dump_json(indent=2),
    )

    try:
        response = await client.aio.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_GeminiReportContent,
            ),
        )
        raw = _GeminiReportContent.model_validate_json(response.text)
    except genai_errors.APIError:
        return _fail_safe(evidence)
    except ValidationError:
        return _fail_safe(evidence)

    return MedicationReport(
        profile_used=evidence.profile_used,
        drug_name=evidence.drug_identity.input_name,
        summary=raw.summary,
        key_findings=raw.key_findings,
        warnings=raw.warnings,
        contraindications=raw.contraindications,
        recalls=raw.recalls,
        adverse_events=raw.adverse_events,
        interactions=raw.interactions,
        limitations=raw.limitations,
        sources_used=evidence.metadata.successful_sources,
        completeness_score=evidence.metadata.completeness_score,
    )
