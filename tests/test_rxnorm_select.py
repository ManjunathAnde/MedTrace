"""select_rxcui: exact name, then first IN, then first candidate (PROJECT.md §5.3)."""

from backend.apis.rxnorm import select_rxcui


def test_exact_name_beats_earlier_ingredient():
    # RxNorm search=1 for "omeprazole" returns esomeprazole first.
    candidates = [("283742", "esomeprazole", "IN"), ("7646", "omeprazole", "IN")]
    assert select_rxcui("omeprazole", candidates) == "7646"


def test_exact_name_is_case_insensitive():
    candidates = [("1", "warfarin sodium", "PIN"), ("11289", "warfarin", "IN")]
    assert select_rxcui("Warfarin", candidates) == "11289"
    assert select_rxcui("  WARFARIN ", candidates) == "11289"


def test_no_exact_name_falls_back_to_first_ingredient():
    candidates = [("1", "drug a 10 mg", "SCD"), ("2", "drug a", "IN"), ("3", "drug b", "IN")]
    assert select_rxcui("druga", candidates) == "2"


def test_no_ingredient_falls_back_to_first_candidate():
    candidates = [("1", "x 10 mg", "SCD"), ("2", "x tablet", "SCDF")]
    assert select_rxcui("y", candidates) == "1"


def test_single_candidate():
    assert select_rxcui("anything", [("42", "other", "BN")]) == "42"


def test_failed_properties_cannot_win_exact_match():
    candidates = [("1", None, None), ("2", "omeprazole", "IN")]
    assert select_rxcui("omeprazole", candidates) == "2"
    assert select_rxcui("missing", [("1", None, None), ("2", "b", "SCD")]) == "1"
