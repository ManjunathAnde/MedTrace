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

import logging
import re
from dataclasses import dataclass

from backend.llm.safety_classifier import classify_safety
from backend.models.classification import SafetyClassificationResult, Wall1Result
from backend.models.enums import (
    SafetyCategory,
    SafetyClassifierType,
    SafetyDecision,
    Wall1Action,
)

logger = logging.getLogger(__name__)


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
            # "safe for me", "safe for my [X]", "is it safe for me" all match via substring
            re.compile(r"\bsafe for (me|my)\b", re.IGNORECASE),
            re.compile(r"\bsafe during\b", re.IGNORECASE),
            re.compile(r"\bsafe with my\b", re.IGNORECASE),
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


# --- v2 wall 1 (PROJECT.md Section 5.1) ---
# Replaces the v1 rules above once /investigate is rewired (check_safety stays
# until then). Rules only block or escalate, never clear. Checked in this order.

_WALL1_SELF_HARM = ("kill myself", "want to die", "end my life", "commit suicide")
_WALL1_PERSONAL_ADVICE = (
    "how much should i give my",
    "how much should i take",
    "what dose for my",
    "should i take",
    "should i stop",
    "what medication should",
    "recommend me",
    "is it safe for me",
    "do i need",
)
_WALL1_ESCALATE = ("overdose", "lethal", "how many pills", "fatal dose")


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    # Whole words, case-insensitive, any run of whitespace between words.
    words = r"\s+".join(re.escape(word) for word in phrase.split())
    return re.compile(rf"\b{words}\b", re.IGNORECASE)


_WALL1_RULES: list[tuple[Wall1Action, SafetyCategory | None, tuple[str, ...]]] = [
    (Wall1Action.BLOCK, SafetyCategory.SELF_HARM_RISK, _WALL1_SELF_HARM),
    (Wall1Action.BLOCK, SafetyCategory.PERSONAL_ADVICE, _WALL1_PERSONAL_ADVICE),
    (Wall1Action.ESCALATE, None, _WALL1_ESCALATE),
]
_WALL1_PATTERNS = [
    (action, category, phrase, _phrase_pattern(phrase))
    for action, category, phrases in _WALL1_RULES
    for phrase in phrases
]


def check_wall1(query: str) -> Wall1Result:
    """Wall 1 rule filter: BLOCK (with category), ESCALATE, or PASS to wall 2."""
    for action, category, phrase, pattern in _WALL1_PATTERNS:
        if pattern.search(query):
            logger.info("wall1 %s category=%s matched=%r", action.value,
                        category.value if category else None, phrase)
            return Wall1Result(action=action, category=category, matched=phrase)
    return Wall1Result(action=Wall1Action.PASS, category=None, matched=None)
