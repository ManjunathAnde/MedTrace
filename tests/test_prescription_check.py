"""Prescription Check pure parts (PROJECT.md §9, §14 CP5): input, candidate search, severity, cache key."""

from types import SimpleNamespace

import pytest

from backend.cache.report_cache import build_prescription_cache_key
from backend.core.prescription_check import (
    FOOTER,
    combined_provider,
    find_pair_candidates,
    input_outcome,
    match_names,
    pair_card,
    parse_drug_list,
    severity_for,
    sort_by_severity,
)
from backend.models.evidence import DrugIdentity, EvidenceItem


def _identity(name: str, ingredients: list[str], brands: list[str]) -> DrugIdentity:
    return DrugIdentity(input_name=name, normalized_name=name, generic_name=None, rxcui="1",
                        ingredients=ingredients, brand_names=brands)


def _passage(text: str, section: str = "drug_interactions", product: str = "A", id: str = "E1") -> EvidenceItem:
    return EvidenceItem(
        id=id, internal_id="x", product=product, ingredient=None, rxcui="1", source="dailymed_label",
        section=section, text=text, url="https://dailymed.example", label_title=None, label_set_id=None,
        label_effective_date=None, retrieved_at="2026-10-21T00:00:00+00:00",
    )


CIPRO = _identity("ciprofloxacin", ["ciprofloxacin"], ["Cipro"])
TIZANIDINE = _identity("tizanidine", ["tizanidine"], ["Zanaflex"])


# --- 9.1 input ---

def test_parse_trims_drops_empty_and_dedupes_case_insensitive():
    assert parse_drug_list(["  Warfarin ", "", "warfarin", "   ", "Aspirin", "ASPIRIN"]) == ["Warfarin", "Aspirin"]


@pytest.mark.parametrize("count,outcome", [(0, "TOO_FEW"), (1, "TOO_FEW"), (2, None), (5, None), (6, "TOO_MANY")])
def test_input_count_rules(count, outcome):
    assert input_outcome([f"drug{i}" for i in range(count)]) == outcome


def test_footer_exact():
    assert FOOTER == "Class-level interactions were not checked."


# --- 9.4 candidate search ---

def test_match_names_are_ingredients_and_brands_lowercased_short_names_dropped():
    identity = _identity("x", ["Iron", "ASA", "Aspirin"], ["Bayer", "Aspirin"])
    assert match_names(identity) == ["iron", "aspirin", "bayer"]


def test_candidate_found_by_ingredient_case_insensitive():
    cipro_passages = [_passage("Concomitant administration with TIZANIDINE is contraindicated.",
                               section="contraindications", product="ciprofloxacin")]
    found = find_pair_candidates(cipro_passages, match_names(CIPRO), [], match_names(TIZANIDINE))
    assert [(c.item.section, c.matched_name) for c in found] == [("contraindications", "tizanidine")]


def test_candidate_found_by_brand_name():
    found = find_pair_candidates([_passage("Do not use with Zanaflex.")], match_names(CIPRO),
                                 [], match_names(TIZANIDINE))
    assert [c.matched_name for c in found] == ["zanaflex"]


def test_both_directions_a_first_then_b():
    a = [_passage("Tizanidine levels rise.", id="E1")]
    b = [_passage("Ciprofloxacin inhibits CYP1A2.", id="E2", product="tizanidine")]
    found = find_pair_candidates(a, match_names(CIPRO), b, match_names(TIZANIDINE))
    assert [c.item.id for c in found] == ["E1", "E2"]


@pytest.mark.parametrize("text", [
    "Tizanidines are not mentioned here.",      # name inside a longer word
    "Pretizanidine compounds.",                 # name after letters
    "No mention of the other drug at all.",
])
def test_word_boundaries_prevent_partial_matches(text):
    assert find_pair_candidates([_passage(text)], [], [], match_names(TIZANIDINE)) == []


def test_name_under_four_chars_never_matches():
    short = _identity("x", ["ASA"], ["Ecc"])
    assert find_pair_candidates([_passage("Avoid ASA and Ecc together.")], [], [], match_names(short)) == []


def test_no_candidates_in_either_direction_is_empty():
    amox = _identity("amoxicillin", ["amoxicillin"], ["Amoxil"])
    levo = _identity("levothyroxine", ["levothyroxine"], ["Synthroid"])
    found = find_pair_candidates([_passage("Probenecid decreases renal tubular secretion.")], match_names(amox),
                                 [_passage("Calcium carbonate may reduce absorption.")], match_names(levo))
    assert found == []


def test_one_candidate_per_passage_even_if_several_names_match():
    found = find_pair_candidates([_passage("Tizanidine (Zanaflex) is contraindicated.")], [],
                                 [], match_names(TIZANIDINE))
    assert len(found) == 1


# --- 9.7 severity, one test per row ---

@pytest.mark.parametrize("section", ["boxed_warning", "contraindications"])
def test_high_from_section(section):
    assert severity_for([_passage("Some text.", section=section, id="E4")]) == ("High", f"section {section} (E4)")


def test_high_from_contraindicated_text_in_any_section():
    assert severity_for([_passage("Use is CONTRAINDICATED with tizanidine.", section="warnings")]) == (
        "High", "text has 'contraindicated' (E1)")


@pytest.mark.parametrize("phrase", ["avoid", "do not use", "not recommended", "should not be used"])
def test_high_from_avoid_phrases(phrase):
    assert severity_for([_passage(f"Concomitant use: {phrase.upper()} with X.")]) == ("High", f"text has '{phrase}' (E1)")


@pytest.mark.parametrize("phrase", ["monitor", "adjust", "reduce the dose", "dose reduction",
                                    "increased risk", "may increase", "may decrease"])
def test_moderate_phrases(phrase):
    assert severity_for([_passage(f"Clinicians should {phrase} when combined.")]) == (
        "Moderate", f"text has '{phrase}' (E1)")


def test_info_when_no_signal():
    assert severity_for([_passage("Both drugs were studied together.")]) == ("Info", "no severity signal")
    assert severity_for([]) == ("Info", "no severity signal")


def test_highest_wins_and_first_passage_at_that_level_is_shown():
    cited = [
        _passage("Monitor INR closely.", id="E1"),
        _passage("Avoid concomitant use.", id="E2"),
        _passage("Not recommended.", id="E3"),
    ]
    assert severity_for(cited) == ("High", "text has 'avoid' (E2)")


# --- cache key (owner note: sorted resolved drug list) ---

def test_prescription_cache_key_is_order_independent_and_versioned():
    assert build_prescription_cache_key(["2551", "35636"]) == build_prescription_cache_key(["35636", "2551"])
    assert build_prescription_cache_key(["35636", "2551"]) == "v4:prescription_check:2551,35636"


# --- 9.6 after verification, one test per row ---

def test_documented_with_kept_claims_is_a_card_with_severity():
    cited = [_passage("Concomitant use is contraindicated.", section="contraindications", id="E28")]
    assert pair_card("INTERACTION_DOCUMENTED", cited) == ("High", "section contraindications (E28)")


def test_documented_with_no_kept_claims_needs_review():
    assert pair_card("INTERACTION_DOCUMENTED", []) is None


def test_no_interaction_stated_with_kept_claims_is_an_info_card():
    assert pair_card("NO_INTERACTION_STATED", [_passage("No clinically important effect.")]) == (
        "Info", "Label states no clinically significant interaction")


def test_no_interaction_stated_with_no_kept_claims_needs_review():
    assert pair_card("NO_INTERACTION_STATED", []) is None


@pytest.mark.parametrize("cited", [[], [_passage("Avoid use.")]])
def test_unclear_or_no_finding_needs_review(cited):
    assert pair_card("UNCLEAR", cited) is None
    assert pair_card(None, cited) is None


def test_cards_sorted_high_moderate_info_stable():
    cards = [SimpleNamespace(severity=s, n=n) for n, s in
             enumerate(["Info", "High", "Moderate", "High", "Info"])]
    assert [(c.severity, c.n) for c in sort_by_severity(cards)] == [
        ("High", 1), ("High", 3), ("Moderate", 2), ("Info", 0), ("Info", 4)]


@pytest.mark.parametrize("providers,expected", [
    (["gemini", "gemini"], "gemini"), (["gemini", "groq"], "groq"), ([None, "gemini"], "gemini"),
    ([None], None), ([], None),
])
def test_combined_verifier_provider(providers, expected):
    assert combined_provider(providers) == expected


# --- 9.7 no-effect statements never score as a signal (2026-10-22, live pantoprazole + clopidogrel) ---

# Verbatim passages from today's labels (pantoprazole E27, clopidogrel E49), cited by the 3 kept claims.
PANTOPRAZOLE_E27 = (
    "Clopidogrel Clinical Impact: Concomitant administration of pantoprazole and clopidogrel in healthy subjects "
    "had no clinically important effect on exposure to the active metabolite of clopidogrel or clopidogrel-induced "
    "platelet inhibition [see Clinical Pharmacology ( 12.3 )] . Intervention: No dose adjustment of clopidogrel is "
    "necessary when administered with an approved dose of Pantoprazole."
)
CLOPIDOGREL_E49 = (
    "Dexlansoprazole, lansoprazole, and pantoprazole had less effect on the antiplatelet activity of clopidogrel "
    "than did omeprazole or esomeprazole [see Warnings and Precautions (5.1) and Clinical Pharmacology (12.3) ]. "
    "7.3 Opioids As with other oral P2Y 12 inhibitors, coadministration of opioid agonists delay and reduce the "
    "absorption of clopidogrel, presumably because of slowed gastric emptying, resulting in reduced exposure to its "
    "metabolites [see Clinical Pharmacology ( 12.3 )] ."
)


def test_pantoprazole_clopidogrel_documented_is_info_not_moderate():
    # claims 1 and 2 cite E27, claim 3 cites E49; the finding stays the agent's (no override)
    cited = [_passage(PANTOPRAZOLE_E27, id="E27", product="pantoprazole"),
             _passage(PANTOPRAZOLE_E27, id="E27", product="pantoprazole"),
             _passage(CLOPIDOGREL_E49, id="E49", product="clopidogrel")]
    assert severity_for(cited) == ("Info", "no severity signal")
    assert pair_card("INTERACTION_DOCUMENTED", cited) == ("Info", "no severity signal")


@pytest.mark.parametrize("text", [
    "No dose adjustment of clopidogrel is necessary when administered with an approved dose of Pantoprazole.",
    "No dose adjustments are needed.",
    "Coadministration had no clinically significant effect on exposure.",
    "The change was not clinically relevant.",
])
def test_no_effect_statement_alone_has_no_severity_signal(text):
    assert severity_for([_passage(text)]) == ("Info", "no severity signal")


def test_real_signal_next_to_no_effect_statement_still_fires():
    text = "No dose adjustment of warfarin is necessary. Monitor INR closely."
    assert severity_for([_passage(text)]) == ("Moderate", "text has 'monitor' (E1)")


def test_contraindicated_stays_high_with_no_effect_statement_present():
    text = "No dose adjustment is necessary for most patients. Concomitant use with tizanidine is contraindicated."
    assert severity_for([_passage(text)]) == ("High", "text has 'contraindicated' (E1)")
    assert severity_for([_passage("No dose adjustment is necessary.", section="contraindications")]) == (
        "High", "section contraindications (E1)")
