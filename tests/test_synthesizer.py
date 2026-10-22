"""Synthesizer (PROJECT.md §7, §12.3): prompt building and the failure rule (LLM mocked)."""

import asyncio

from backend.llm import synthesizer
from backend.llm.providers import ProvidersUnavailableError
from backend.llm.synthesizer import (
    SYNTHESIS_FAILED_GAP,
    SynthInput,
    build_synthesizer_prompt,
    format_evidence_line,
    synthesize_claims,
)
from backend.models.claims import Claim, ClaimSet
from backend.models.evidence import EvidenceItem


def _item(eid: str, section: str = "boxed_warning", source: str = "dailymed_label") -> EvidenceItem:
    return EvidenceItem(
        id=eid, internal_id="abc123def456", product="Ozempic", ingredient=None, rxcui="1991307",
        source=source, section=section,
        text="In rodents, semaglutide causes thyroid C-cell tumors.",
        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=x", label_title="OZEMPIC",
        label_set_id="x", label_effective_date="2026-07-30", retrieved_at="2026-10-21T00:00:00+00:00",
    )


def _input(question: str = "Why does Ozempic have a boxed warning?", evidence=None) -> SynthInput:
    return SynthInput(question=question, intent="warnings", product="Ozempic",
                      evidence=[_item("E1")] if evidence is None else evidence)


def test_evidence_line_format():
    assert format_evidence_line(_item("E3")) == (
        "[E3] source=dailymed_label section=boxed_warning | "
        "In rodents, semaglutide causes thyroid C-cell tumors."
    )


def test_prompt_fills_every_placeholder_once():
    prompt = build_synthesizer_prompt(_input())
    assert "QUESTION: Why does Ozempic have a boxed warning?" in prompt
    assert "INTENT: warnings" in prompt and "MEDICATION: Ozempic" in prompt
    assert prompt.rstrip().endswith("[E1] source=dailymed_label section=boxed_warning | "
                                    "In rodents, semaglutide causes thyroid C-cell tumors.")
    for placeholder in ("{question}", "{intent}", "{product}", "{evidence_items}"):
        assert placeholder not in prompt
    # JSON output example keeps its braces
    assert '{"status": "ANSWERED" | "PARTIAL" | "INSUFFICIENT_EVIDENCE"' in prompt


def test_question_text_is_never_substituted_again():
    prompt = build_synthesizer_prompt(_input(question="What is {intent} and {evidence_items}?"))
    assert "QUESTION: What is {intent} and {evidence_items}?" in prompt
    assert prompt.count("[E1]") == 1


def test_prompt_has_claim_cap_rule():
    assert "11. Write at most 8 claims. Prioritize boxed warning and contraindications." in (
        build_synthesizer_prompt(_input())
    )


def test_both_providers_failing_gives_insufficient_evidence(monkeypatch):
    async def fail(*args, **kwargs):
        raise ProvidersUnavailableError("gemini: 429; groq: 401")

    monkeypatch.setattr(synthesizer, "complete_json", fail)
    claim_set, provider = asyncio.run(synthesize_claims(_input()))
    assert provider is None
    assert claim_set == ClaimSet(status="INSUFFICIENT_EVIDENCE", claims=[], gaps=[SYNTHESIS_FAILED_GAP])


def test_no_evidence_makes_no_llm_call(monkeypatch):
    async def must_not_run(*args, **kwargs):
        raise AssertionError("LLM called without evidence")

    monkeypatch.setattr(synthesizer, "complete_json", must_not_run)
    claim_set, provider = asyncio.run(synthesize_claims(_input(evidence=[])))
    assert claim_set.status == "INSUFFICIENT_EVIDENCE" and claim_set.claims == [] and provider is None


def test_result_passes_through_with_provider(monkeypatch):
    expected = ClaimSet(status="ANSWERED", claims=[Claim(
        text="In rodents, semaglutide causes thyroid C-cell tumors.", evidence_id="E1",
        quote="In rodents, semaglutide causes thyroid C-cell tumors.")], gaps=[])

    async def ok(prompt, schema, max_output_tokens):
        assert schema is ClaimSet and max_output_tokens == synthesizer.SYNTHESIZER_MAX_OUTPUT_TOKENS
        return expected, "groq"

    monkeypatch.setattr(synthesizer, "complete_json", ok)
    assert asyncio.run(synthesize_claims(_input())) == (expected, "groq")


def test_claims_module_imports_nothing_from_backend():
    import ast
    import inspect

    import backend.models.claims as claims_module

    tree = ast.parse(inspect.getsource(claims_module))
    imported = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    imported += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in imported if m and m.startswith("backend")]
