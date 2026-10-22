"""
Synthesizer (PROJECT.md Sections 7, 12.3): evidence items -> claims.

One typed async function on providers.py (Gemini first, Groq fallback). Every
claim cites one evidence item and quotes it; the verifier (CP4) checks them.
Never falls back to free text: if both providers fail, the result is
INSUFFICIENT_EVIDENCE with a fixed gap. Replaces the risk_analyst.py report.
"""

import logging
import re

from pydantic import BaseModel

from backend.llm.providers import (
    SYNTHESIZER_MAX_OUTPUT_TOKENS,
    Provider,
    ProvidersUnavailableError,
    complete_json,
)
from backend.models.claims import ClaimSet
from backend.models.evidence import EvidenceItem

logger = logging.getLogger(__name__)

SYNTHESIS_FAILED_GAP = "The answer could not be generated. Please try again."
NO_EVIDENCE_GAP = "No FDA evidence was retrieved for this question."

# PROJECT.md Section 12.3, verbatim, plus rule 11 (owner, 2026-10-21: keeps the
# answer inside the synthesizer's output-token budget) and rule 12 (owner,
# 2026-10-22: Groq dropped exposure limits and the verifier cut the claims). The
# rule 12 example is made up on purpose: no benchmark question matches it.
_SYNTHESIZER_PROMPT = """\
You answer medication questions using ONLY the evidence passages provided. You have no other knowledge. If something is not in the passages, you do not know it.

RULES
1. Write the answer as a list of claims. Each claim states ONE fact.
2. Each claim cites exactly one evidence_id and includes a quote copied WORD FOR WORD from that passage, 5 to 30 words long. Never alter the quote.
3. Claim text may use plain language but must not add meaning beyond the passage.
4. Keep every qualifier exactly: "in rodents", "unknown whether", "may", "rarely", "in patients with". Never turn uncertainty into certainty.
5. Copy all numbers, doses, and percentages exactly as written.
6. Never add facts from your own knowledge: no drug class, use, mechanism, or brand information unless a passage states it.
7. Never give instructions or recommendations to the reader ("you should", "avoid taking", "talk to your doctor").
8. To state that something is ABSENT, cite an evidence item whose source is "absence".
9. If part of the question is not covered by the passages, add a short description of that part to "gaps". Do not guess.
10. If no claims can be supported, return status "INSUFFICIENT_EVIDENCE" with an empty claims list.
11. Write at most 8 claims. Prioritize boxed warning and contraindications.
12. When a passage limits a finding to a species, population, dose, exposure level, or duration, keep that limit in the claim's wording. Example: passage "In rats, Drug X caused liver tumors at exposures 10 times the maximum human dose after 2 years" -> claim "In rats, Drug X caused liver tumors at exposures 10 times the maximum human dose after 2 years", not "Drug X caused liver tumors".

Order claims: boxed warning, indications, contraindications, warnings, interactions, dosage, adverse event reports, recalls.

OUTPUT: only JSON:
{"status": "ANSWERED" | "PARTIAL" | "INSUFFICIENT_EVIDENCE", "claims": [{"text": "...", "evidence_id": "E1", "quote": "..."}], "gaps": ["..."]}

QUESTION: {question}
INTENT: {intent}
MEDICATION: {product}
EVIDENCE:
{evidence_items}
"""

_PLACEHOLDER = re.compile(r"\{(question|intent|product|evidence_items)\}")


class SynthInput(BaseModel):
    question: str
    intent: str
    product: str
    evidence: list[EvidenceItem]


def format_evidence_line(item: EvidenceItem) -> str:
    """Section 7 line format: [E3] source=dailymed_label section=boxed_warning | {text}"""
    return f"[{item.id}] source={item.source} section={item.section} | {item.text}"


def build_synthesizer_prompt(synth_input: SynthInput) -> str:
    # One pass, so text inside the question can never be substituted again.
    values = {
        "question": synth_input.question,
        "intent": synth_input.intent,
        "product": synth_input.product,
        "evidence_items": "\n".join(format_evidence_line(i) for i in synth_input.evidence),
    }
    return _PLACEHOLDER.sub(lambda m: values[m.group(1)], _SYNTHESIZER_PROMPT)


async def synthesize_claims(synth_input: SynthInput) -> tuple[ClaimSet, Provider | None]:
    """Claims from evidence, with the provider used (None when no LLM call produced them)."""
    if not synth_input.evidence:
        return ClaimSet(status="INSUFFICIENT_EVIDENCE", claims=[], gaps=[NO_EVIDENCE_GAP]), None
    try:
        claim_set, provider = await complete_json(
            build_synthesizer_prompt(synth_input), ClaimSet, SYNTHESIZER_MAX_OUTPUT_TOKENS
        )
    except ProvidersUnavailableError as exc:
        logger.warning("synthesizer unavailable (%s); returning INSUFFICIENT_EVIDENCE", exc)
        return ClaimSet(status="INSUFFICIENT_EVIDENCE", claims=[], gaps=[SYNTHESIS_FAILED_GAP]), None
    logger.info(
        "synthesizer status=%s claims=%d gaps=%d provider=%s evidence=%d",
        claim_set.status, len(claim_set.claims), len(claim_set.gaps), provider,
        len(synth_input.evidence),
    )
    return claim_set, provider
