"""
Two-stage safety filter for the Medication Intelligence Agent.

Stage 1 — deterministic rule engine: zero-cost, no LLM, instant.
          Organized by unsafe intent category rather than flat keyword list.
          Uses regex for flexible matching but each rule carries an explicit
          human-readable category and reason.

Stage 2 — Gemini fallback: called only on Stage 1 miss.
          Handles edge cases the rule engine cannot express deterministically,
          e.g. "my doctor told me to quit this drug, thoughts?"

Public interface: async check_safety(query) -> SafetyClassificationResult
"""

import re
from dataclasses import dataclass

from backend.llm.safety_classifier import classify_safety
from backend.models.classification import SafetyClassificationResult
from backend.models.enums import SafetyClassifierType, SafetyDecision


@dataclass(frozen=True)
class _SafetyRule:
    category: str
    reason: str
    patterns: list[re.Pattern[str]]


# Each rule captures one unsafe intent category.
# Patterns within a category are ORed — any match fires the rule.
# All patterns are compiled once at module load time.
_RULES: list[_SafetyRule] = [
    _SafetyRule(
        category="dosage_request",
        reason="Dosage recommendation request",
        patterns=[
            re.compile(r"\bwhat dosage\b", re.IGNORECASE),
            re.compile(r"\bwhat dose\b", re.IGNORECASE),
            re.compile(r"\bhow (much|many).{0,20}\b(should i|can i|do i)\b", re.IGNORECASE),
        ],
    ),
    _SafetyRule(
        category="medication_start_stop_change",
        reason="Medication start, stop, or change request",
        patterns=[
            re.compile(r"\bshould i (take|start|stop|use|switch|try|quit)\b", re.IGNORECASE),
            re.compile(r"\bcan i (take|stop|start|switch|quit|use)\b", re.IGNORECASE),
            re.compile(r"\bdo i (need|have to|should)\b", re.IGNORECASE),
        ],
    ),
    _SafetyRule(
        category="treatment_recommendation",
        reason="Treatment or medication recommendation request",
        patterns=[
            re.compile(r"\bwhat (medication|drug|medicine|treatment) should\b", re.IGNORECASE),
            re.compile(r"\bwhich (medication|drug|medicine) should i\b", re.IGNORECASE),
            re.compile(
                r"\bwhich (medication|drug|medicine) is (right|better|best) for\b",
                re.IGNORECASE,
            ),
            re.compile(r"\brecommend (me|a|an)\b", re.IGNORECASE),
            re.compile(r"\bwhat should i take\b", re.IGNORECASE),
        ],
    ),
    _SafetyRule(
        category="patient_specific_advice",
        reason="Patient-specific medical advice request",
        patterns=[
            re.compile(r"\bis it safe for (me|my)\b", re.IGNORECASE),
            re.compile(r"\bsafe for (me|my (child|kid|baby|son|daughter))\b", re.IGNORECASE),
            re.compile(r"\bfor my (condition|disease|age|weight|history)\b", re.IGNORECASE),
            re.compile(
                r"\bcan my (child|kid|baby|son|daughter|wife|husband|mother|father)\b",
                re.IGNORECASE,
            ),
        ],
    ),
    _SafetyRule(
        category="medical_emergency",
        reason="Medical emergency guidance request",
        patterns=[
            re.compile(r"\bswallowed\b", re.IGNORECASE),
            re.compile(r"\boverdose\b", re.IGNORECASE),
            re.compile(r"\bpoison (control|center)\b", re.IGNORECASE),
        ],
    ),
    _SafetyRule(
        category="diagnosis_request",
        reason="Diagnosis request",
        patterns=[
            re.compile(r"\bdo i have\b", re.IGNORECASE),
            re.compile(r"\bam i (sick|ill|diabetic|hypertensive|at risk)\b", re.IGNORECASE),
            re.compile(r"\bdiagnose me\b", re.IGNORECASE),
        ],
    ),
]


async def check_safety(query: str) -> SafetyClassificationResult:
    """
    Stage 1: iterate rules; return UNSAFE immediately on first match.
    Stage 2: delegate to Gemini only when no rule matches.

    The filter has no knowledge of retrieval profiles, API clients, or
    report generation — its only output is SafetyClassificationResult.
    """
    for rule in _RULES:
        for pattern in rule.patterns:
            if pattern.search(query):
                return SafetyClassificationResult(
                    decision=SafetyDecision.UNSAFE,
                    reason=rule.reason,
                    classifier=SafetyClassifierType.RULE,
                )

    return await classify_safety(query)
