"""/investigate and /prescription-check wiring (PROJECT.md §4, §6, §8, §10): status rule, intent sources, RxNorm outage."""

from fastapi.testclient import TestClient

import backend.core.prescription_check as prescription_check
import backend.main as main
from backend.apis.rxnorm import RxNormServiceError
from backend.core.router import INTENT_NAMES, SOURCES_BY_PROFILE, final_status
from backend.evidence.store import (
    FAERS_TOP_REACTIONS,
    FAERS_TOP_REACTIONS_FULL,
    LABEL_SECTIONS,
    RECALLS,
    RECALLS_FULL,
)
from backend.models.classification import IntentClassificationResult, SafetyVerdict
from backend.models.enums import InvestigateStatus, ProfileType, SafetyCategory


# --- status rules (§8) ---

def test_no_kept_claims_is_insufficient_evidence():
    assert final_status(0, 0, []) == InvestigateStatus.INSUFFICIENT_EVIDENCE
    assert final_status(0, 3, ["x"]) == InvestigateStatus.INSUFFICIENT_EVIDENCE


def test_any_cut_or_gap_is_partial():
    assert final_status(2, 1, []) == InvestigateStatus.PARTIAL
    assert final_status(2, 0, ["Not covered: price"]) == InvestigateStatus.PARTIAL


def test_all_kept_and_no_gaps_is_answered():
    assert final_status(3, 0, []) == InvestigateStatus.ANSWERED


# --- intent to sources (§6 table) ---

def test_sources_follow_section_6_table():
    s = SOURCES_BY_PROFILE
    assert s[ProfileType.FULL_INVESTIGATION].label_sections == list(LABEL_SECTIONS)
    assert s[ProfileType.FULL_INVESTIGATION].faers_top_reactions == FAERS_TOP_REACTIONS_FULL
    assert s[ProfileType.FULL_INVESTIGATION].recalls == RECALLS_FULL
    assert s[ProfileType.WARNINGS_REVIEW].label_sections == ["boxed_warning", "warnings"]
    assert s[ProfileType.CONTRAINDICATIONS_REVIEW].label_sections == ["contraindications", "boxed_warning"]
    assert s[ProfileType.INTERACTION_INVESTIGATION].label_sections == ["drug_interactions"]
    assert s[ProfileType.ADVERSE_EVENT_INVESTIGATION].faers_top_reactions == FAERS_TOP_REACTIONS
    assert s[ProfileType.RECALL_INVESTIGATION].recalls == RECALLS
    for profile in (ProfileType.WARNINGS_REVIEW, ProfileType.CONTRAINDICATIONS_REVIEW,
                    ProfileType.INTERACTION_INVESTIGATION):
        assert s[profile].faers_top_reactions is None and s[profile].recalls is None
    assert s[ProfileType.ADVERSE_EVENT_INVESTIGATION].label_sections == []
    assert s[ProfileType.RECALL_INVESTIGATION].label_sections == []


def test_every_profile_has_sources_and_an_intent_name():
    assert set(SOURCES_BY_PROFILE) == set(ProfileType) == set(INTENT_NAMES)


# --- RxNorm outage fails loud (the one mocked test, §10, CLAUDE.md §10) ---

def test_rxnorm_outage_returns_5xx(monkeypatch):
    async def safe(query):
        return SafetyVerdict(safety=SafetyCategory.SAFE, safety_reason="label question"), "groq"

    async def extract(query):
        return ["warfarin"], "groq"

    async def intent(query):
        return IntentClassificationResult(
            profile=ProfileType.WARNINGS_REVIEW, confidence=1.0, reason="warnings"), "groq"

    async def no_cache(key):
        return None

    async def rxnorm_down(name):
        raise RxNormServiceError("RxNorm returned HTTP 503")

    async def must_not_run(*args, **kwargs):
        raise AssertionError("no retrieval or synthesis after an RxNorm outage")

    monkeypatch.setattr(main, "classify_safety_category", safe)
    monkeypatch.setattr(main, "extract_medication_names", extract)
    monkeypatch.setattr(main, "classify_query_intent", intent)
    monkeypatch.setattr(main, "get_cached_response", no_cache)
    monkeypatch.setattr(main, "fetch_drug_identity", rxnorm_down)
    monkeypatch.setattr(main, "fetch_label_evidence", must_not_run)
    monkeypatch.setattr(main, "synthesize_claims", must_not_run)

    response = TestClient(main.app).post("/investigate", json={"query": "What are the boxed warnings for warfarin?"})
    assert response.status_code == 503
    assert response.json()["error"] == "rxnorm_unavailable"


def test_prescription_check_rxnorm_outage_returns_5xx(monkeypatch):
    async def rxnorm_down(name):
        raise RxNormServiceError("RxNorm returned HTTP 503")

    async def must_not_run(*args, **kwargs):
        raise AssertionError("no retrieval or LLM call after an RxNorm outage")

    monkeypatch.setattr(prescription_check, "fetch_drug_identity", rxnorm_down)
    monkeypatch.setattr(prescription_check, "fetch_label_evidence", must_not_run)
    monkeypatch.setattr(main, "evaluate_pair", must_not_run)

    response = TestClient(main.app).post("/prescription-check", json={"drugs": ["tizanidine", "ciprofloxacin"]})
    assert response.status_code == 503
    assert response.json()["error"] == "rxnorm_unavailable"
