"""
Citation verifier (PROJECT.md Section 8).

Knows nothing about drugs: it sees claims and the passages they cite. Its only
backend/ imports are backend/models/claims.py and backend/llm/providers.py.

  L0 (code)  evidence_id is a known passage            -> else CUT_BAD_ID
  L1 (code)  quote is 5-30 words and, normalized, a
             substring of the normalized passage        -> else CUT_QUOTE
  L3 (code)  claim text has no directive phrase          -> else CUT_DIRECTIVE
  L2 (LLM)   one batched support check on the claims
             that passed L0, L1, L3 (Section 12.5)      -> NOT_SUPPORTED or no result: CUT_SUPPORT

The code layers run first so the LLM only sees claims that could be kept.
Gemini first, Groq fallback (providers.py). Both fail: the remaining claims are
cut with reason "verifier unavailable". Every cut is logged.
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel

from backend.llm.providers import (
    VERIFIER_MAX_OUTPUT_TOKENS,
    Provider,
    ProvidersUnavailableError,
    complete_json,
)
from backend.models.claims import Claim, VerifiedClaim, VerifiedClaimSet

logger = logging.getLogger(__name__)

QUOTE_MIN_WORDS = 5
QUOTE_MAX_WORDS = 30
VERIFIER_UNAVAILABLE = "verifier unavailable"

# Section 5.1 wall 3: claims must not instruct the reader.
_DIRECTIVE_PHRASES = ("you should", "you must", "you can take", "your doctor", "give your", "stop taking")
_DIRECTIVE_PATTERNS = [
    re.compile(r"\b" + r"\s+".join(map(re.escape, p.split())) + r"\b", re.IGNORECASE)
    for p in _DIRECTIVE_PHRASES
]

_QUOTE_CHARS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-",
})

# PROJECT.md Section 12.5; the claims block is generated in place of the
# "{for each claim: ...}" line.
_SUPPORT_PROMPT = """\
You check whether each claim is fully supported by its passage. You are strict. Use only the passage, never outside knowledge.

A claim is SUPPORTED only if every part of it is stated in or directly follows from the passage. It is NOT_SUPPORTED if it:
- adds any fact, number, condition, or detail the passage does not state
- drops or weakens a qualifier in a way that changes meaning (for example, the passage says "in rodents" or "unknown whether" and the claim does not)
- states something with more certainty than the passage
- contradicts the passage

Return only JSON: {"results": [{"index": 0, "verdict": "SUPPORTED" | "NOT_SUPPORTED", "reason": "<one short sentence>"}]}
Return one result for every claim index.

CLAIMS:
"""


class SupportResult(BaseModel):
    index: int
    verdict: Literal["SUPPORTED", "NOT_SUPPORTED"]
    reason: str


class SupportResults(BaseModel):
    results: list[SupportResult]


def normalize(text: str) -> str:
    """L1 normalization: lowercase, straight quotes, en/em dash to '-', collapse whitespace, strip."""
    return " ".join(text.translate(_QUOTE_CHARS).lower().split())


def check_quote(quote: str, passage: str) -> str | None:
    """L1. None if the quote passes, else the reason it fails."""
    words = len(normalize(quote).split())
    if words < QUOTE_MIN_WORDS:
        return f"quote has {words} words (minimum {QUOTE_MIN_WORDS})"
    if words > QUOTE_MAX_WORDS:
        return f"quote has {words} words (maximum {QUOTE_MAX_WORDS})"
    if normalize(quote) not in normalize(passage):
        return "quote not found in the cited passage"
    return None


def find_directive(text: str) -> str | None:
    """L3. The directive phrase in the claim text, if any."""
    for phrase, pattern in zip(_DIRECTIVE_PHRASES, _DIRECTIVE_PATTERNS):
        if pattern.search(text):
            return phrase
    return None


def build_support_prompt(claims: list[Claim], passages: dict[str, str]) -> str:
    block = "\n".join(
        f"[{index}] CLAIM: {claim.text}\nPASSAGE: {passages[claim.evidence_id]}"
        for index, claim in enumerate(claims)
    )
    return _SUPPORT_PROMPT + block + "\n"


def _verified(claim: Claim, verdict: str, reason: str) -> VerifiedClaim:
    return VerifiedClaim(**claim.model_dump(), verdict=verdict, reason=reason)


async def _check_support(
    claims: list[Claim], passages: dict[str, str]
) -> tuple[list[VerifiedClaim], Provider | None]:
    """L2: one batched call. Missing or NOT_SUPPORTED results are cut."""
    if not claims:
        return [], None
    try:
        results, provider = await complete_json(
            build_support_prompt(claims, passages), SupportResults, VERIFIER_MAX_OUTPUT_TOKENS
        )
    except ProvidersUnavailableError as exc:
        logger.warning("verifier L2 unavailable (%s); cutting %d claims", exc, len(claims))
        return [_verified(c, "CUT_SUPPORT", VERIFIER_UNAVAILABLE) for c in claims], None

    by_index = {r.index: r for r in results.results}
    verified = []
    for index, claim in enumerate(claims):
        result = by_index.get(index)
        if result is None:
            verified.append(_verified(claim, "CUT_SUPPORT", "no support result returned"))
        elif result.verdict == "SUPPORTED":
            verified.append(_verified(claim, "KEPT", result.reason))
        else:
            verified.append(_verified(claim, "CUT_SUPPORT", result.reason))
    return verified, provider


async def verify(claims: list[Claim], passages: dict[str, str]) -> VerifiedClaimSet:
    """Check every claim against the passage it cites; claim order is kept."""
    decided: dict[int, VerifiedClaim] = {}
    for_support: list[tuple[int, Claim]] = []
    for position, claim in enumerate(claims):
        if claim.evidence_id not in passages:
            decided[position] = _verified(claim, "CUT_BAD_ID", f"unknown evidence id {claim.evidence_id!r}")
            continue
        quote_problem = check_quote(claim.quote, passages[claim.evidence_id])
        if quote_problem:
            decided[position] = _verified(claim, "CUT_QUOTE", quote_problem)
            continue
        directive = find_directive(claim.text)
        if directive:
            decided[position] = _verified(claim, "CUT_DIRECTIVE", f"directive phrase {directive!r}")
            continue
        for_support.append((position, claim))

    supported, provider = await _check_support([c for _, c in for_support], passages)
    for (position, _), verified_claim in zip(for_support, supported):
        decided[position] = verified_claim

    ordered = [decided[position] for position in range(len(claims))]
    kept = [c for c in ordered if c.verdict == "KEPT"]
    cut = [c for c in ordered if c.verdict != "KEPT"]
    for c in cut:
        logger.warning("verifier cut %s reason=%r claim=%r quote=%r evidence_id=%s",
                       c.verdict, c.reason, c.text, c.quote, c.evidence_id)
    logger.info("verifier kept=%d cut=%d provider=%s", len(kept), len(cut), provider)
    return VerifiedClaimSet(
        kept=kept, cut=cut, claims_total=len(claims), claims_kept=len(kept),
        verifier_provider=provider,
    )
