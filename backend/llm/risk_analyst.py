"""
Gemini Risk Analyst — with Groq fallback on transient provider failures.

Receives MedicationEvidence (structured API data) and returns MedicationReport
(structured LLM analysis). The LLM fills the 8 analytical fields only; Python
assembles the final report by copying the 4 metadata fields directly from
evidence so that profile_used, drug_name, completeness_score, and sources_used
are always ground-truth values, never LLM estimates.

Retry policy: no retries — the evidence-collection phase already took time.
Transient Gemini provider failures trigger Groq fallback. All other API errors
and validation failures return _fail_safe so that LLM unavailability never
raises to the caller.
"""

import logging
import os
import time

import groq as groq_sdk
from google import genai
from google.genai import errors as genai_errors, types
from pydantic import ValidationError

from backend.llm.groq_client import (
    _GROQ_MODEL,
    TRANSIENT_GEMINI_NETWORK_ERRORS,
    get_groq_client,
    is_transient_gemini_error,
)
from backend.models.base import BaseSchema
from backend.models.enums import ProfileType
from backend.models.evidence import MedicationEvidence
from backend.models.report import MedicationReport

_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

MAX_BOXED_WARNINGS = 3
MAX_CONTRAINDICATIONS = 5
MAX_PRECAUTIONS = 5
MAX_INTERACTIONS = 3
MAX_RECALLS = 5
MAX_ADVERSE_EVENTS = 10
MAX_LABEL_SECTION_CHARS = 1200

logger = logging.getLogger(__name__)

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

_GROQ_JSON_SUFFIX = (
    "\n\nReturn JSON only with exactly these fields (all required, use empty list [] when not applicable):\n"
    '{"summary": "<string>", "key_findings": ["<string>", ...], '
    '"warnings": ["<string>", ...], "contraindications": ["<string>", ...], '
    '"recalls": ["<string>", ...], "adverse_events": ["<string>", ...], '
    '"interactions": ["<string>", ...], "limitations": ["<string>", ...]}'
)


class _GeminiReportContent(BaseSchema):
    """Private schema for Gemini and Groq structured output.

    Covers only the 8 analytical fields. The 4 metadata fields (profile_used,
    drug_name, completeness_score, sources_used) are copied from evidence in
    Python — the LLM never sets them."""

    summary: str
    key_findings: list[str]
    warnings: list[str]
    contraindications: list[str]
    recalls: list[str]
    adverse_events: list[str]
    interactions: list[str]
    limitations: list[str]


def _fail_safe(evidence: MedicationEvidence) -> MedicationReport:
    logger.warning("  RISK_ANALYST returning fail_safe primary_provider=gemini fallback_provider=fail_safe")
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


def _truncate_at_word_boundary(text: str) -> str:
    if len(text) <= MAX_LABEL_SECTION_CHARS:
        return text
    return text[:MAX_LABEL_SECTION_CHARS].rsplit(" ", 1)[0]


# Condenses evidence only for LLM prompt construction.
# Retrieval outputs remain unchanged.
# Ground-truth counts and metadata are preserved.
def _condense_for_llm(evidence: MedicationEvidence) -> MedicationEvidence:
    """
    Prepare an LLM-friendly evidence copy before prompt serialization.

    Reduces token count for both Gemini and Groq paths while preserving the
    original evidence object and all ground-truth metadata/count fields.
    """
    updates: dict = {}

    if evidence.label_evidence is not None:
        label = evidence.label_evidence
        condensed_label = label.model_copy(update={
            "boxed_warnings": [
                _truncate_at_word_boundary(item)
                for item in label.boxed_warnings[:MAX_BOXED_WARNINGS]
            ],
            "contraindications": [
                _truncate_at_word_boundary(item)
                for item in label.contraindications[:MAX_CONTRAINDICATIONS]
            ],
            "precautions": [
                _truncate_at_word_boundary(item)
                for item in label.precautions[:MAX_PRECAUTIONS]
            ],
            "drug_interactions": [
                _truncate_at_word_boundary(item)
                for item in label.drug_interactions[:MAX_INTERACTIONS]
            ],
        })
        updates["label_evidence"] = condensed_label

    if evidence.adverse_event_evidence is not None:
        ae = evidence.adverse_event_evidence
        updates["adverse_event_evidence"] = ae.model_copy(
            update={"events": ae.events[:MAX_ADVERSE_EVENTS]}
        )

    if evidence.recall_evidence is not None:
        rc = evidence.recall_evidence
        updates["recall_evidence"] = rc.model_copy(
            update={"recalls": rc.recalls[:MAX_RECALLS]}
        )

    return evidence.model_copy(update=updates) if updates else evidence


def _build_prompt(evidence: MedicationEvidence) -> str:
    """Single source of truth for prompt construction. Used by both Gemini and Groq paths."""
    return _PROMPT_TEMPLATE.format(
        profile_name=evidence.profile_used.value,
        profile_instructions=_PROFILE_INSTRUCTIONS[evidence.profile_used],
        evidence_json=evidence.model_dump_json(indent=2),
    )


def _assemble_report(evidence: MedicationEvidence, raw: _GeminiReportContent) -> MedicationReport:
    """
    Shared assembly step — Gemini and Groq paths converge here after
    _GeminiReportContent.model_validate_json() succeeds. Zero provider
    branching from this point forward.
    """
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


async def _try_groq_report(evidence: MedicationEvidence) -> MedicationReport:
    """
    Groq fallback for Gemini provider failures. Builds the prompt independently via
    _build_prompt() — same template and evidence serialization as the Gemini
    path. Returns _fail_safe on any Groq error so that a Groq outage never
    raises to the caller.
    """
    t_groq = time.perf_counter()
    try:
        client = get_groq_client()
        groq_prompt = _build_prompt(evidence) + _GROQ_JSON_SUFFIX
        # Qwen reasoning models may emit reasoning tokens before JSON.
        # Disable reasoning so JSON Object Mode returns a valid JSON object
        # compatible with _GeminiReportContent validation.
        response = await client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "user", "content": groq_prompt}],
            response_format={"type": "json_object"},
            reasoning_effort="none",
        )
        content = (response.choices[0].message.content or "").strip()
        # Defensive strip: json_object mode normally suppresses thinking blocks,
        # but strip them if present to guarantee clean JSON input to the validator.
        if "</think>" in content:
            content = content.split("</think>", 1)[1].strip()
        raw = _GeminiReportContent.model_validate_json(content)
        duration_ms = round((time.perf_counter() - t_groq) * 1000, 1)
        logger.info(
            "  RISK_ANALYST Groq fallback: model=%s duration_ms=%.1f primary_provider=gemini fallback_provider=groq",
            _GROQ_MODEL,
            duration_ms,
        )
        return _assemble_report(evidence, raw)
    except ValidationError as exc:
        logger.warning(
            "  RISK_ANALYST Groq fallback ValidationError primary_provider=gemini fallback_provider=fail_safe: %s",
            exc,
        )
        return _fail_safe(evidence)
    except (groq_sdk.APIStatusError, groq_sdk.APIConnectionError) as exc:
        logger.warning(
            "  RISK_ANALYST Groq fallback API error primary_provider=gemini fallback_provider=fail_safe (%s): %s",
            type(exc).__name__,
            exc,
        )
        return _fail_safe(evidence)
    except KeyError:
        logger.warning(
            "  RISK_ANALYST Groq fallback failed: GROQ_API_KEY not set primary_provider=gemini fallback_provider=fail_safe"
        )
        return _fail_safe(evidence)
    except Exception as exc:
        logger.warning(
            "  RISK_ANALYST Groq fallback unexpected error primary_provider=gemini fallback_provider=fail_safe (%s): %s",
            type(exc).__name__,
            exc,
        )
        return _fail_safe(evidence)


async def generate_report(evidence: MedicationEvidence) -> MedicationReport:
    """
    Analyze structured medication evidence and return a MedicationReport.

    Condenses evidence before serialization so that both the Gemini and Groq
    paths receive a prompt within their token budgets. On transient Gemini
    provider failures, falls back to Groq. Validation failures return
    _fail_safe so that LLM unavailability never raises to the caller.
    """
    evidence = _condense_for_llm(evidence)
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    t_total = time.perf_counter()

    try:
        response = await client.aio.models.generate_content(
            model=_MODEL,
            contents=_build_prompt(evidence),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_GeminiReportContent,
            ),
        )
        raw = _GeminiReportContent.model_validate_json(response.text)
        duration_ms = round((time.perf_counter() - t_total) * 1000, 1)
        logger.info(
            "  RISK_ANALYST diag: model=%s duration_ms=%.1f primary_provider=gemini fallback_provider=none",
            _MODEL,
            duration_ms,
        )
        return _assemble_report(evidence, raw)
    except genai_errors.APIError as exc:
        api_error_type = f"{type(exc).__name__}({getattr(exc, 'code', '?')})"
        if is_transient_gemini_error(exc):
            logger.warning(
                "  RISK_ANALYST Gemini provider failure detected primary_provider=gemini error=%s",
                api_error_type,
            )
            logger.warning(
                "  RISK_ANALYST Attempting Groq fallback primary_provider=gemini"
            )
            return await _try_groq_report(evidence)
        logger.warning(
            "  RISK_ANALYST Gemini API error primary_provider=gemini fallback_provider=fail_safe: %s",
            api_error_type,
        )
        return _fail_safe(evidence)
    except TRANSIENT_GEMINI_NETWORK_ERRORS as exc:
        logger.warning(
            "  RISK_ANALYST Gemini provider failure detected primary_provider=gemini error=%s: %s",
            type(exc).__name__,
            exc,
        )
        logger.warning(
            "  RISK_ANALYST Attempting Groq fallback primary_provider=gemini"
        )
        return await _try_groq_report(evidence)
    except ValidationError as exc:
        logger.warning(
            "  RISK_ANALYST Gemini ValidationError primary_provider=gemini fallback_provider=fail_safe: %s",
            exc,
        )
        return _fail_safe(evidence)
