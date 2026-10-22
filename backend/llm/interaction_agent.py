"""
Interaction agent (PROJECT.md Sections 9.5, 12.4): one pair's candidate
passages -> a finding and claims.

Called only for pairs where code found candidates (Section 9.4). One typed
async function on providers.py (Gemini first, Groq fallback; invalid output is
retried once per provider there). Both providers fail: None, and the caller
puts the pair in needs_review. The verifier checks every claim afterwards.
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel

from backend.llm.providers import (
    INTERACTION_MAX_OUTPUT_TOKENS,
    Provider,
    ProvidersUnavailableError,
    complete_json,
)
from backend.models.claims import Claim
from backend.models.evidence import EvidenceItem

logger = logging.getLogger(__name__)

NOT_EVALUATED_REASON = "could not be evaluated automatically."

Finding = Literal["INTERACTION_DOCUMENTED", "NO_INTERACTION_STATED", "UNCLEAR"]

# PROJECT.md Section 12.4, verbatim, plus rule 6 (owner, 2026-10-21: keeps the
# answer inside the agent's output-token budget).
_INTERACTION_PROMPT = """\
You judge whether FDA label passages document an interaction between two medications. Use ONLY the passages provided. You have no other knowledge.

MEDICATION A: {product_a} (ingredients: {ingredients_a})
MEDICATION B: {product_b} (ingredients: {ingredients_b})

RULES
1. Decide one finding:
   - INTERACTION_DOCUMENTED: a passage describes an interaction, risk, contraindication, or caution involving both medications (by ingredient or brand name).
   - NO_INTERACTION_STATED: a passage explicitly states no clinically significant interaction between them.
   - UNCLEAR: a name is mentioned but the passages do not clearly say either of the above.
2. Write claims that describe what the passages say about the two medications together. Each claim states ONE fact, cites exactly one evidence_id, and includes a quote copied WORD FOR WORD from that passage, 5 to 30 words long.
3. Keep qualifiers and numbers exactly as written. Never add mechanisms, severity words, or advice that the passage does not state.
4. Never give instructions to the reader.
5. If the finding is UNCLEAR, return an empty claims list.
6. Write at most 5 claims.

OUTPUT: only JSON:
{"finding": "INTERACTION_DOCUMENTED" | "NO_INTERACTION_STATED" | "UNCLEAR", "claims": [{"text": "...", "evidence_id": "E12", "quote": "..."}]}

PASSAGES:
{candidate_passages}
"""

_PLACEHOLDER = re.compile(r"\{(product_a|ingredients_a|product_b|ingredients_b|candidate_passages)\}")


class PairInput(BaseModel):
    product_a: str
    ingredients_a: list[str]
    product_b: str
    ingredients_b: list[str]
    passages: list[EvidenceItem]  # the pair's candidates, E-IDs already assigned


class InteractionResult(BaseModel):
    """What the LLM returns (Section 12.4 OUTPUT)."""
    finding: Finding
    claims: list[Claim]


class PairFinding(BaseModel):
    """Section 9.5; the pair is set by code, never by the LLM."""
    pair: tuple[str, str]
    finding: Finding
    claims: list[Claim]


def format_passage_line(item: EvidenceItem) -> str:
    """Section 9.5 line format: [E12] product=warfarin section=drug_interactions | {text}"""
    return f"[{item.id}] product={item.product} section={item.section} | {item.text}"


def build_interaction_prompt(pair_input: PairInput) -> str:
    # One pass, so text inside a passage can never be substituted again.
    values = {
        "product_a": pair_input.product_a,
        "ingredients_a": ", ".join(pair_input.ingredients_a),
        "product_b": pair_input.product_b,
        "ingredients_b": ", ".join(pair_input.ingredients_b),
        "candidate_passages": "\n".join(format_passage_line(i) for i in pair_input.passages),
    }
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], _INTERACTION_PROMPT)


def to_pair_finding(pair: tuple[str, str], result: InteractionResult) -> PairFinding:
    """Rule 5 enforced in code: an UNCLEAR finding carries no claims."""
    claims = result.claims
    if result.finding == "UNCLEAR" and claims:
        logger.warning("interaction agent: UNCLEAR for %s with %d claims; claims dropped", pair, len(claims))
        claims = []
    return PairFinding(pair=pair, finding=result.finding, claims=claims)


async def evaluate_pair(pair_input: PairInput) -> tuple[PairFinding | None, Provider | None]:
    """The pair's finding and the provider used; (None, None) when both providers fail."""
    pair = (pair_input.product_a, pair_input.product_b)
    try:
        result, provider = await complete_json(
            build_interaction_prompt(pair_input), InteractionResult, INTERACTION_MAX_OUTPUT_TOKENS
        )
    except ProvidersUnavailableError as exc:
        logger.warning("interaction agent unavailable for %s (%s); %s", pair, exc, NOT_EVALUATED_REASON)
        return None, None
    finding = to_pair_finding(pair, result)
    logger.info("interaction agent pair=%s finding=%s claims=%d provider=%s passages=%d",
                pair, finding.finding, len(finding.claims), provider, len(pair_input.passages))
    return finding, provider
