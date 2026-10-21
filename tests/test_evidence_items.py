"""Evidence items (PROJECT.md §6): internal_id stability, label/absence items, FAERS items."""

import hashlib

from backend.evidence.store import (
    build_faers_items,
    build_label_items,
    make_internal_id,
)
from backend.models.evidence import AdverseEvent, AdverseEventEvidence, LabelEvidence

RETRIEVED_AT = "2026-10-20T12:00:00+00:00"
FAERS_URL = 'https://api.fda.gov/drug/event.json?search=patient.drug.openfda.generic_name:"warfarin"'
DISCLAIMER = "FAERS reports do not establish that the drug caused the event."


def _label(**sections: list[str]) -> LabelEvidence:
    fields = dict(
        boxed_warnings=[], indications_and_usage=[], dosage_and_administration=[],
        contraindications=[], precautions=[], drug_interactions=[],
    )
    fields.update(sections)
    return LabelEvidence(
        label_title="WARFARIN SODIUM TABLET [CARDINAL HEALTH 107, LLC]",
        set_id="cdbbc317-35d3-42ba-94f0-c83891358529",
        effective_date="2025-11-06",
        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=cdbbc317-35d3-42ba-94f0-c83891358529",
        tie_breaker=1,
        skipped_set_ids=[],
        **fields,
    )


def test_internal_id_is_sha1_prefix_of_joined_fields():
    expected = hashlib.sha1(b"dailymed_label|set-1|warnings|3|Some text").hexdigest()[:12]
    assert make_internal_id("dailymed_label", "set-1", "warnings", 3, "Some text") == expected
    # Fixed value: changes only if the id formula changes.
    assert make_internal_id("faers", None, "faers_total", 0, "x") == (
        hashlib.sha1(b"faers||faers_total|0|x").hexdigest()[:12]
    )


def test_internal_id_stable_and_sensitive_to_each_field():
    base = ("dailymed_label", "set-1", "warnings", 0, "Text")
    assert make_internal_id(*base) == make_internal_id(*base)
    variants = [
        ("absence", "set-1", "warnings", 0, "Text"),
        ("dailymed_label", "set-2", "warnings", 0, "Text"),
        ("dailymed_label", "set-1", "contraindications", 0, "Text"),
        ("dailymed_label", "set-1", "warnings", 1, "Text"),
        ("dailymed_label", "set-1", "warnings", 0, "Text."),
    ]
    ids = {make_internal_id(*v) for v in variants}
    assert make_internal_id(*base) not in ids and len(ids) == len(variants)


def test_label_items_follow_section_order_and_skip_unrequested():
    label = _label(
        drug_interactions=["7 DRUG INTERACTIONS Aspirin increases bleeding risk with warfarin."],
        boxed_warnings=["WARNING: BLEEDING RISK Warfarin can cause major or fatal bleeding."],
        dosage_and_administration=["2 DOSAGE AND ADMINISTRATION Individualize the dose."],
    )
    items = build_label_items(
        "warfarin", "11289", label, ["drug_interactions", "boxed_warning"], RETRIEVED_AT
    )
    assert [i.section for i in items] == ["boxed_warning", "drug_interactions"]
    assert items[1].text == "Aspirin increases bleeding risk with warfarin."
    for item in items:
        assert item.source == "dailymed_label" and item.id == ""
        assert item.label_set_id == label.set_id and item.label_title == label.label_title
        assert item.label_effective_date == "2025-11-06" and item.url == label.url
        assert item.ingredient is None and item.rxcui == "11289"
        assert item.retrieved_at == RETRIEVED_AT


def test_missing_requested_section_gives_absence_item():
    label = _label(boxed_warnings=["WARNING: BLEEDING RISK Warfarin can cause major or fatal bleeding."])
    items = build_label_items("warfarin", "11289", label, ["boxed_warning", "contraindications"], RETRIEVED_AT)
    absence = items[-1]
    assert absence.source == "absence" and absence.section == "contraindications"
    assert absence.text == (
        "The retrieved warfarin label (WARFARIN SODIUM TABLET [CARDINAL HEALTH 107, LLC], "
        "set ID cdbbc317-35d3-42ba-94f0-c83891358529) contains no contraindications section."
    )


def test_section_with_only_short_text_counts_as_missing():
    label = _label(drug_interactions=["7 DRUG INTERACTIONS None."])
    items = build_label_items("warfarin", "11289", label, ["drug_interactions"], RETRIEVED_AT)
    assert [i.source for i in items] == ["absence"]


def test_long_section_chunks_have_distinct_stable_ids():
    text = "5 WARNINGS AND PRECAUTIONS " + " ".join(
        f"Warning {n} describes a distinct risk in about one hundred characters of plain text here." for n in range(20)
    )
    label = _label(precautions=[text])
    first = build_label_items("warfarin", "11289", label, ["warnings"], RETRIEVED_AT)
    second = build_label_items("warfarin", "11289", label, ["warnings"], RETRIEVED_AT)
    assert len(first) > 1 and all(len(i.text) <= 600 for i in first)
    assert [i.internal_id for i in first] == [i.internal_id for i in second]
    assert len({i.internal_id for i in first}) == len(first)


def test_faers_items_top_10_then_total_with_disclaimer():
    events = [AdverseEvent(term=f"REACTION {n}", count=100 - n, serious=False) for n in range(15)]
    evidence = AdverseEventEvidence(events=events, total_count=5000)
    items = build_faers_items("warfarin", "11289", "warfarin", evidence, FAERS_URL, RETRIEVED_AT)
    assert len(items) == 11
    assert [i.section for i in items] == ["faers_reaction"] * 10 + ["faers_total"]
    assert items[0].text == (
        "FAERS: 100 reports list 'REACTION 0' for warfarin (retrieved 2026-10-20). " + DISCLAIMER
    )
    assert items[-1].text == (
        "FAERS: 5000 total reports mention warfarin (retrieved 2026-10-20). " + DISCLAIMER
    )
    for item in items:
        assert item.source == "faers" and item.text.endswith(DISCLAIMER)
        assert item.ingredient == "warfarin" and item.url == FAERS_URL
        assert item.label_set_id is None and item.label_title is None


def test_no_faers_reports_gives_absence_item():
    evidence = AdverseEventEvidence(events=[], total_count=0)
    items = build_faers_items("Zorvax", "1", "zorvax", evidence, FAERS_URL, RETRIEVED_AT)
    assert len(items) == 1
    assert items[0].source == "absence" and items[0].section == "faers"
    assert items[0].text == "No FAERS reports were found for zorvax as of 2026-10-20."
