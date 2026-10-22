"""Verifier (PROJECT.md §8, §14 CP4): L0, L1, L3, L2 handling (LLM mocked), status rules, imports."""

import ast
import asyncio
import inspect

import pytest

import backend.models.claims as claims_module
import backend.verifier.verifier as verifier_module
from backend.core.router import final_status
from backend.llm.providers import ProvidersUnavailableError
from backend.models.claims import Claim
from backend.models.enums import InvestigateStatus
from backend.verifier.verifier import (
    SupportResult,
    SupportResults,
    build_support_prompt,
    check_quote,
    find_directive,
    normalize,
    verify,
)

OZEMPIC = (
    "In rodents, semaglutide causes dose-dependent and treatment-duration-dependent thyroid "
    "C-cell tumors at clinically relevant exposures. It is unknown whether OZEMPIC causes "
    "thyroid C-cell tumors, including medullary thyroid carcinoma (MTC), in humans."
)
CONTRACT = (
    "This Agreement shall automatically renew for successive one-year terms unless either party "
    "gives written notice of non-renewal at least 60 days before the end of the then-current term."
)
REAL_QUOTE = "In rodents, semaglutide causes dose-dependent and treatment-duration-dependent thyroid C-cell tumors"


def _claim(text: str, quote: str = REAL_QUOTE, evidence_id: str = "E1") -> Claim:
    return Claim(text=text, evidence_id=evidence_id, quote=quote)


def _mock_l2(monkeypatch, verdicts: dict[int, str] | None = None, calls: list | None = None):
    """Replace the L2 LLM call; verdicts by index (missing index -> no result returned)."""
    async def fake_complete_json(prompt, schema, max_output_tokens):
        assert schema is SupportResults
        if calls is not None:
            calls.append(prompt)
        results = [SupportResult(index=i, verdict=v, reason="mocked") for i, v in (verdicts or {}).items()]
        return SupportResults(results=results), "groq"

    monkeypatch.setattr(verifier_module, "complete_json", fake_complete_json)


def _run(claims, passages=None):
    return asyncio.run(verify(claims, passages or {"E1": OZEMPIC}))


# --- L1 quote check ---

def test_real_quote_passes_l1():
    assert check_quote(REAL_QUOTE, OZEMPIC) is None


def test_curly_quotes_dashes_and_extra_whitespace_still_match():
    passage = "Patients’ risk — “unknown”   whether it  applies in humans."
    assert check_quote("patients' risk - \"unknown\" whether it applies", passage) is None
    assert normalize("  A–B \n  C ") == "a-b c"


def test_fake_quote_fails_l1():
    assert check_quote("Semaglutide is proven to cause thyroid cancer in humans", OZEMPIC) == (
        "quote not found in the cited passage")


@pytest.mark.parametrize("quote,words", [
    ("semaglutide causes dose-dependent tumors", 4),
    (" ".join(["word"] * 31), 31),
])
def test_quote_length_outside_5_to_30_words_fails(quote, words):
    passage = quote + " and more"
    assert check_quote(quote, passage).startswith(f"quote has {words} words")


# --- L3 directive guard ---

@pytest.mark.parametrize("text", [
    "You should take this with food.",
    "You must not crush the tablet.",
    "You can take it at night.",
    "Ask your doctor before use.",
    "Give your child the dose on the label.",
    "Stop taking it if a rash appears.",
])
def test_directive_phrases_found(text):
    assert find_directive(text) is not None


def test_label_wording_without_directive_phrases_passes_l3():
    assert find_directive("Patients should be counseled regarding the potential risk of MTC.") is None
    assert find_directive("Youshould is not a phrase") is None


# --- verify(): L0, L1, L3 verdicts, order, L2 handling ---

def test_unknown_evidence_id_is_cut_bad_id(monkeypatch):
    _mock_l2(monkeypatch)
    result = _run([_claim("In rodents, semaglutide causes thyroid C-cell tumors.", evidence_id="E9")])
    assert [c.verdict for c in result.cut] == ["CUT_BAD_ID"]


def test_fake_quote_is_cut_quote_and_never_sent_to_l2(monkeypatch):
    calls = []
    _mock_l2(monkeypatch, calls=calls)
    result = _run([_claim("Semaglutide causes thyroid cancer.", quote="Semaglutide is proven to cause thyroid cancer")])
    assert [c.verdict for c in result.cut] == ["CUT_QUOTE"] and calls == []
    assert result.verifier_provider is None


def test_directive_claim_is_cut_directive(monkeypatch):
    _mock_l2(monkeypatch, {0: "SUPPORTED"})
    result = _run([_claim("You should take this with food.")])
    assert [c.verdict for c in result.cut] == ["CUT_DIRECTIVE"]


def test_supported_claim_kept_and_order_preserved(monkeypatch):
    _mock_l2(monkeypatch, {0: "SUPPORTED", 1: "NOT_SUPPORTED"})
    claims = [
        _claim("Bad id claim.", evidence_id="E7"),
        _claim("In rodents, semaglutide causes thyroid C-cell tumors."),
        _claim("Semaglutide causes thyroid C-cell tumors."),
    ]
    result = _run(claims)
    assert [c.text for c in result.kept] == ["In rodents, semaglutide causes thyroid C-cell tumors."]
    assert [c.verdict for c in result.cut] == ["CUT_BAD_ID", "CUT_SUPPORT"]
    assert (result.claims_total, result.claims_kept, result.verifier_provider) == (3, 1, "groq")


def test_missing_l2_result_is_cut_support(monkeypatch):
    _mock_l2(monkeypatch, {})
    result = _run([_claim("In rodents, semaglutide causes thyroid C-cell tumors.")])
    assert [(c.verdict, c.reason) for c in result.cut] == [("CUT_SUPPORT", "no support result returned")]


def test_l2_unavailable_cuts_remaining_claims(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise ProvidersUnavailableError("gemini: 429; groq: 401")

    monkeypatch.setattr(verifier_module, "complete_json", unavailable)
    result = _run([_claim("In rodents, semaglutide causes thyroid C-cell tumors.")])
    assert [(c.verdict, c.reason) for c in result.cut] == [("CUT_SUPPORT", "verifier unavailable")]
    assert result.verifier_provider is None and result.claims_kept == 0


def test_support_prompt_lists_each_claim_with_its_full_passage():
    prompt = build_support_prompt([_claim("A claim.")], {"E1": OZEMPIC})
    assert prompt.rstrip().endswith(f"[0] CLAIM: A claim.\nPASSAGE: {OZEMPIC}")
    assert "{for each claim" not in prompt


# --- status rules (§8) on verifier output ---

def test_all_claims_cut_is_insufficient_evidence(monkeypatch):
    _mock_l2(monkeypatch, {0: "NOT_SUPPORTED"})
    result = _run([_claim("Semaglutide causes thyroid C-cell tumors."), _claim("x", evidence_id="E5")])
    assert result.claims_kept == 0
    assert final_status(result.claims_kept, len(result.cut), []) == InvestigateStatus.INSUFFICIENT_EVIDENCE


def test_some_cut_is_partial_and_none_cut_is_answered(monkeypatch):
    _mock_l2(monkeypatch, {0: "SUPPORTED", 1: "NOT_SUPPORTED"})
    claims = [_claim("In rodents, semaglutide causes thyroid C-cell tumors."), _claim("Semaglutide causes tumors.")]
    result = _run(claims)
    assert final_status(result.claims_kept, len(result.cut), []) == InvestigateStatus.PARTIAL
    _mock_l2(monkeypatch, {0: "SUPPORTED"})
    result = _run(claims[:1])
    assert final_status(result.claims_kept, len(result.cut), []) == InvestigateStatus.ANSWERED


# --- domain test: contract clause (§8), LLM mocked ---

def test_contract_clause_true_claim_kept_false_claim_cut(monkeypatch):
    calls = []
    _mock_l2(monkeypatch, {0: "SUPPORTED", 1: "NOT_SUPPORTED"}, calls)
    true_claim = Claim(
        text="The agreement renews automatically each year unless notice is given 60 days before the term ends.",
        evidence_id="C1",
        quote="automatically renew for successive one-year terms unless either party gives written notice",
    )
    false_claim = Claim(
        text="Either party can cancel at any time with 30 days notice.",
        evidence_id="C1",
        quote="either party gives written notice of non-renewal at least 60 days",
    )
    result = asyncio.run(verify([true_claim, false_claim], {"C1": CONTRACT}))
    assert [c.text for c in result.kept] == [true_claim.text]
    assert [c.verdict for c in result.cut] == ["CUT_SUPPORT"]
    assert CONTRACT in calls[0]  # both claims reached L2 with the full passage


# --- import boundary (§8, CLAUDE.md §8.5) ---

def _backend_imports(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    return {n for n in names if n.startswith("backend")}


def test_verifier_imports_only_claims_and_providers():
    assert _backend_imports(verifier_module) == {"backend.models.claims", "backend.llm.providers"}


def test_claims_module_imports_nothing_from_backend():
    assert _backend_imports(claims_module) == set()
