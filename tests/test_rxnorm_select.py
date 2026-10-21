"""RxNorm pure rules (PROJECT.md §5.3): select_rxcui and filter_brands_by_ingredients."""

from backend.apis.rxnorm import filter_brands_by_ingredients, select_rxcui


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


# filter_brands_by_ingredients: brand kept only if its ingredient set equals the product's.

def test_combination_brands_dropped_for_single_ingredient():
    omeprazole = {"7646"}
    brands = [
        ("Prilosec", {"7646"}),
        ("Yosprala", {"1191", "7646"}),
        ("Talicia", {"9384", "723", "7646"}),
        ("Konvomep", {"36676", "7646"}),
    ]
    assert filter_brands_by_ingredients(omeprazole, brands) == ["Prilosec"]


def test_combination_product_keeps_same_set_brand_any_order():
    tylenol_pm = {"161", "3498"}
    brands = [("Tylenol PM", {"3498", "161"}), ("Tylenol", {"161"}), ("X", {"161", "3498", "1"})]
    assert filter_brands_by_ingredients(tylenol_pm, brands) == ["Tylenol PM"]


def test_failed_brand_lookup_dropped():
    assert filter_brands_by_ingredients({"7646"}, [("A", None), ("B", {"7646"})]) == ["B"]


def test_no_brands():
    assert filter_brands_by_ingredients({"7646"}, []) == []
