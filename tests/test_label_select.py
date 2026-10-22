"""Label tie-breakers (PROJECT.md §5.4): title_tier and order_spls, with real DailyMed titles."""

from backend.apis.dailymed import order_spls, title_tier


def test_esomeprazole_title_is_not_a_match_for_omeprazole():
    title = "ESOMEPRAZOLE MAGNESIUM CAPSULE, DELAYED RELEASE [EXAMPLE LABS]"
    assert title_tier(title, "omeprazole", single_ingredient=True) == 4


def test_single_product_title_is_tier_1():
    title = "OMEPRAZOLE (OMEPRAZOLE MAGNESIUM) CAPSULE, DELAYED RELEASE [WALGREEN COMPANY]"
    assert title_tier(title, "omeprazole", single_ingredient=True) == 1


def test_digifab_is_only_a_mention_of_digoxin():
    title = "DIGIFAB (OVINE DIGOXIN IMMUNE FAB) INJECTION, POWDER, LYOPHILIZED, FOR SOLUTION [BTG INTERNATIONAL INC.]"
    assert title_tier(title, "digoxin", single_ingredient=True) == 3


def test_combination_title_drops_to_tier_2_for_single_ingredient():
    title = "TRAMADOL HYDROCHLORIDE AND ACETAMINOPHEN TABLET [PREFERRED PHARMACEUTICALS INC.]"
    assert title_tier(title, "tramadol", single_ingredient=True) == 2


def test_combination_title_is_tier_1_for_combination_product():
    title = "ACETAMINOPHEN AND DIPHENHYDRAMINE HYDROCHLORIDE TABLET [EXAMPLE LABS]"
    assert title_tier(title, "acetaminophen", single_ingredient=False) == 1


def test_multi_product_title_drops_to_tier_2():
    title = (
        "OZEMPIC (ORAL SEMAGLUTIDE) TABLET RYBELSUS (ORAL SEMAGLUTIDE) TABLET "
        "[NOVO NORDISK PHARMACEUTICAL INDUSTRIES, INC.]"
    )
    assert title_tier(title, "Ozempic", single_ingredient=True) == 2


def test_matching_is_case_insensitive_and_whole_word():
    assert title_tier("Ozempic (semaglutide) injection [X]", "OZEMPIC", True) == 1
    assert title_tier("WARFARINX TABLET [X]", "warfarin", True) == 4


def test_order_is_stable_within_a_tier():
    spls = [
        {"setid": "combo", "title": "TRAMADOL HYDROCHLORIDE AND ACETAMINOPHEN TABLET [A]"},
        {"setid": "first", "title": "TRAMADOL HYDROCHLORIDE TABLET [B]"},
        {"setid": "other", "title": "SOMETHING ELSE [C]"},
        {"setid": "second", "title": "TRAMADOL HYDROCHLORIDE TABLET, COATED [D]"},
    ]
    ordered = order_spls(spls, "tramadol", single_ingredient=True)
    assert [(tier, spl["setid"]) for tier, spl in ordered] == [
        (1, "first"), (1, "second"), (2, "combo"), (4, "other"),
    ]
