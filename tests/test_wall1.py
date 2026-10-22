"""Safety wall 1 rules (PROJECT.md §5.1): check_wall1."""

import pytest

from backend.models.enums import SafetyCategory, Wall1Action
from backend.safety.filter import check_wall1


@pytest.mark.parametrize("query", [
    "I want to kill myself with my pills",
    "I just want to die",
    "how would I end my life",
    "Could I commit   suicide with this?",
])
def test_self_harm_phrases_block_as_self_harm(query):
    result = check_wall1(query)
    assert result.action == Wall1Action.BLOCK
    assert result.category == SafetyCategory.SELF_HARM_RISK


@pytest.mark.parametrize("query", [
    "How much should I give my 2 year old?",
    "How much should I take for a headache?",
    "What dose for my dog?",
    "Should I take warfarin?",
    "Should I stop taking my lisinopril?",
    "What medication should I use for pain?",
    "Recommend me a sleep aid",
    "Is it safe for me to take ibuprofen?",
    "Do I need to take metformin with food?",
])
def test_personal_advice_phrases_block(query):
    result = check_wall1(query)
    assert result.action == Wall1Action.BLOCK
    assert result.category == SafetyCategory.PERSONAL_ADVICE


@pytest.mark.parametrize("query", [
    "What is the antidote for acetaminophen overdose?",
    "Is this dose lethal?",
    "How many pills are in a bottle?",
    "What is the fatal dose listed for digoxin?",
])
def test_overdose_phrases_escalate_not_block(query):
    result = check_wall1(query)
    assert result.action == Wall1Action.ESCALATE and result.category is None


@pytest.mark.parametrize("query", [
    "Can I take ibuprofen with lisinopril?",   # must reach REDIRECT (dropped v1 "can i take")
    "What are the boxed warnings for warfarin?",
    "Is Eliquis safe during pregnancy?",       # dropped v1 "safe during": wall 2 decides
    "What is the maximum daily dose listed on the acetaminophen label?",
    "Zorvaxitran side effects",
])
def test_other_queries_pass_to_wall2(query):
    result = check_wall1(query)
    assert result.action == Wall1Action.PASS
    assert result.category is None and result.matched is None


def test_self_harm_checked_before_personal_advice():
    result = check_wall1("Should I take all of them? I want to die")
    assert result.category == SafetyCategory.SELF_HARM_RISK


def test_phrases_match_whole_words_only():
    # "do i need" must not fire inside other words
    assert check_wall1("Pseudo i needle test").action == Wall1Action.PASS
    assert check_wall1("What is overdosed in this label?").action == Wall1Action.PASS
