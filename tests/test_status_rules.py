"""Early statuses and drug count rules (PROJECT.md §5.1-5.3, §10): backend/core/router.py."""

import pytest

from backend.core.router import (
    blocked_outcome,
    drug_count_outcome,
    not_recognized_outcome,
    unavailable_outcome,
)
from backend.models.enums import InvestigateStatus, ProfileType, SafetyCategory


def test_zero_drugs_is_no_drug_for_any_intent():
    for profile in ProfileType:
        outcome = drug_count_outcome([], profile)
        assert outcome.status == InvestigateStatus.NO_DRUG
        assert outcome.message == "Please include the medication name in your question."


def test_one_drug_continues_for_any_intent():
    for profile in ProfileType:
        assert drug_count_outcome(["warfarin"], profile) is None


def test_two_drugs_interactions_redirects_with_names():
    outcome = drug_count_outcome(["ibuprofen", "lisinopril"], ProfileType.INTERACTION_INVESTIGATION)
    assert outcome.status == InvestigateStatus.REDIRECT
    assert outcome.redirect.to == "prescription_check"
    assert outcome.redirect.drugs == ["ibuprofen", "lisinopril"]
    assert outcome.message is None and outcome.block_type is None


@pytest.mark.parametrize("profile", [p for p in ProfileType if p != ProfileType.INTERACTION_INVESTIGATION])
def test_two_drugs_other_intents_one_at_a_time(profile):
    outcome = drug_count_outcome(["warfarin", "aspirin", "Tylenol PM"], profile)
    assert outcome.status == InvestigateStatus.ONE_AT_A_TIME
    assert outcome.message == (
        "Please ask about one medication at a time, or use Prescription Check to review several together."
    )
    assert outcome.redirect is None


def test_blocked_outcomes_carry_block_type_and_exact_message():
    advice = blocked_outcome(SafetyCategory.PERSONAL_ADVICE)
    assert advice.status == InvestigateStatus.BLOCKED
    assert advice.block_type == SafetyCategory.PERSONAL_ADVICE
    assert advice.message.startswith("MedTrace provides FDA drug label information, not personal medical advice.")
    harm = blocked_outcome(SafetyCategory.SELF_HARM_RISK)
    assert harm.block_type == SafetyCategory.SELF_HARM_RISK
    assert "988" in harm.message and "call 911" in harm.message


def test_safe_is_not_a_block():
    with pytest.raises(ValueError):
        blocked_outcome(SafetyCategory.SAFE)


def test_unavailable_is_never_blocked():
    outcome = unavailable_outcome()
    assert outcome.status == InvestigateStatus.UNAVAILABLE
    assert outcome.block_type is None
    assert outcome.message == "MedTrace couldn't complete its checks right now. Please try again."


def test_not_recognized_names_the_input():
    outcome = not_recognized_outcome("Zorvaxitran")
    assert outcome.status == InvestigateStatus.NOT_RECOGNIZED
    assert outcome.message == "'Zorvaxitran' wasn't recognized. Check the spelling and try again."
