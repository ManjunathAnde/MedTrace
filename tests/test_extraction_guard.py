"""Extraction guard (PROJECT.md §5.2): validate_extraction, is_plausible_name, prompt build."""

import logging

from backend.llm.medication_extractor import (
    build_extraction_prompt,
    is_plausible_name,
    validate_extraction,
)


def test_corrected_name_is_dropped_and_logged(caplog):
    # The LLM "corrects" warfrin -> warfarin: the guard drops it.
    with caplog.at_level(logging.WARNING, logger="backend.llm.medication_extractor"):
        assert validate_extraction("What are the boxed warnings for warfrin?", ["warfarin"]) == []
    assert "extractor_rejected" in caplog.text and "warfarin" in caplog.text


def test_names_as_typed_are_kept_exactly():
    query = "What are the side effects of Zorvaxitran?"
    assert validate_extraction(query, ["Zorvaxitran"]) == ["Zorvaxitran"]
    assert validate_extraction("Does Tylenol PM interact with Zoloft?", ["Tylenol PM", "Zoloft"]) == [
        "Tylenol PM", "Zoloft",
    ]


def test_match_is_case_insensitive_and_keeps_extracted_casing():
    assert validate_extraction("what about WARFARIN?", ["warfarin"]) == ["warfarin"]


def test_no_rejection_logged_when_all_names_are_in_the_query(caplog):
    with caplog.at_level(logging.WARNING, logger="backend.llm.medication_extractor"):
        validate_extraction("Can I take ibuprofen with lisinopril?", ["ibuprofen", "lisinopril"])
    assert "extractor_rejected" not in caplog.text


def test_dedupes_and_strips_whitespace():
    assert validate_extraction("ibuprofen and ibuprofen", [" ibuprofen ", "ibuprofen"]) == ["ibuprofen"]


def test_empty_and_blank_names_dropped():
    assert validate_extraction("What should I know about my heart medication?", []) == []
    assert validate_extraction("warfarin", ["", "   "]) == []


def test_inferred_class_or_description_names_dropped():
    assert validate_extraction("Are statins safe with alcohol?", ["atorvastatin"]) == []
    assert validate_extraction("my blood pressure pill", ["lisinopril"]) == []


def test_implausible_names_dropped():
    assert validate_extraction("take 500 of it", ["500"]) == []
    assert validate_extraction("vitamin a", ["a"]) == []


def test_is_plausible_name_bounds():
    assert is_plausible_name("Tylenol PM")
    assert is_plausible_name("B12")
    assert not is_plausible_name("x")
    assert not is_plausible_name("12345")
    assert not is_plausible_name("a" * 61)
    assert not is_plausible_name("--")


def test_prompt_substitutes_query_once_and_keeps_json_examples():
    prompt = build_extraction_prompt("Is Eliquis 5mg safe with grapefruit juice?")
    assert prompt.rstrip().endswith("Is Eliquis 5mg safe with grapefruit juice?")
    assert "{query}" not in prompt
    assert '{"drugs": ["Eliquis"]}' in prompt
