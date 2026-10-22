"""Interaction agent pure parts (PROJECT.md §9.5, §12.4): passage format, prompt fill, UNCLEAR guard."""

from backend.llm.interaction_agent import (
    InteractionResult,
    PairInput,
    build_interaction_prompt,
    format_passage_line,
    to_pair_finding,
)
from backend.models.claims import Claim
from backend.models.evidence import EvidenceItem


def _passage(id: str, product: str, section: str, text: str) -> EvidenceItem:
    return EvidenceItem(
        id=id, internal_id="x", product=product, ingredient=None, rxcui="1", source="dailymed_label",
        section=section, text=text, url="https://dailymed.example", label_title=None, label_set_id=None,
        label_effective_date=None, retrieved_at="2026-10-21T00:00:00+00:00",
    )


P1 = _passage("E12", "warfarin", "drug_interactions", "Aspirin may increase the risk of bleeding.")
P2 = _passage("E30", "aspirin", "warnings", "Use with {product_a} anticoagulants such as warfarin.")


def test_passage_line_format():
    assert format_passage_line(P1) == (
        "[E12] product=warfarin section=drug_interactions | Aspirin may increase the risk of bleeding.")


def test_prompt_fills_products_ingredients_and_passages_once():
    prompt = build_interaction_prompt(PairInput(
        product_a="warfarin", ingredients_a=["warfarin"],
        product_b="Tylenol PM", ingredients_b=["acetaminophen", "diphenhydramine"],
        passages=[P1, P2],
    ))
    assert "MEDICATION A: warfarin (ingredients: warfarin)" in prompt
    assert "MEDICATION B: Tylenol PM (ingredients: acetaminophen, diphenhydramine)" in prompt
    assert prompt.rstrip().endswith(format_passage_line(P1) + "\n" + format_passage_line(P2))
    assert "{product_a} anticoagulants" in prompt  # passage text is never substituted
    assert "6. Write at most 5 claims." in prompt
    assert "{candidate_passages}" not in prompt


def test_unclear_finding_drops_claims():
    claim = Claim(text="x", evidence_id="E12", quote="Aspirin may increase the risk of bleeding")
    finding = to_pair_finding(("warfarin", "aspirin"), InteractionResult(finding="UNCLEAR", claims=[claim]))
    assert finding.finding == "UNCLEAR" and finding.claims == []


def test_documented_finding_keeps_claims_and_pair_comes_from_code():
    claim = Claim(text="x", evidence_id="E12", quote="Aspirin may increase the risk of bleeding")
    finding = to_pair_finding(("warfarin", "aspirin"),
                              InteractionResult(finding="INTERACTION_DOCUMENTED", claims=[claim]))
    assert finding.pair == ("warfarin", "aspirin") and finding.claims == [claim]
