"""Evidence items (PROJECT.md §6): internal_id, label/absence/FAERS/recall items, 20-item cap, order, E-IDs."""

import hashlib
from datetime import datetime

from backend.evidence.store import (
    LABEL_SECTIONS,
    MAX_CHUNK_CHARS,
    MAX_EVIDENCE_ITEMS,
    assemble_evidence,
    build_faers_items,
    build_label_items,
    build_recall_items,
    make_internal_id,
)
from backend.models.enums import RecallClassification
from backend.models.evidence import (
    AdverseEvent,
    AdverseEventEvidence,
    LabelEvidence,
    RecallEvidence,
    RecallRecord,
)

RETRIEVED_AT = "2026-10-20T12:00:00+00:00"
FAERS_URL = 'https://api.fda.gov/drug/event.json?search=patient.drug.openfda.generic_name:"warfarin"'
RECALL_URL = 'https://api.fda.gov/drug/enforcement.json?search=product_description:"warfarin"'
DISCLAIMER = "FAERS reports do not establish that the drug caused the event."
ELLIPSIS = "…"


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


def _record(
    n: int,
    reason: str = "Failed dissolution specifications.",
    product: str = "Warfarin Sodium Tablets, 5 mg",
) -> RecallRecord:
    return RecallRecord(
        recall_number=f"D-{n:04d}-2026",
        reason=reason,
        classification=RecallClassification.CLASS_II,
        recall_date=datetime(2026, 9, 30 - n),
        status="Ongoing",
        product_description=product,
    )


# --- internal_id ---

def test_internal_id_is_sha1_prefix_of_joined_fields():
    expected = hashlib.sha1(b"dailymed_label|set-1|warnings|3|Some text").hexdigest()[:12]
    assert make_internal_id("dailymed_label", "set-1", "warnings", 3, "Some text") == expected
    # No set ID (FAERS, recalls) joins as an empty field.
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


# --- label and absence items ---

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
        f"Warning {n} describes a distinct risk in about one hundred characters of plain text here."
        for n in range(20)
    )
    label = _label(precautions=[text])
    first = build_label_items("warfarin", "11289", label, ["warnings"], RETRIEVED_AT)
    second = build_label_items("warfarin", "11289", label, ["warnings"], RETRIEVED_AT)
    assert len(first) > 1 and all(len(i.text) <= MAX_CHUNK_CHARS for i in first)
    assert [i.internal_id for i in first] == [i.internal_id for i in second]
    assert len({i.internal_id for i in first}) == len(first)


# --- FAERS items ---

def test_faers_items_top_n_then_total_with_disclaimer():
    events = [AdverseEvent(term=f"REACTION {n}", count=100 - n, serious=False) for n in range(15)]
    evidence = AdverseEventEvidence(events=events, total_count=5000, query_url=FAERS_URL)
    items = build_faers_items("warfarin", "11289", "warfarin", evidence, 10, RETRIEVED_AT)
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


def test_faers_top_n_follows_caller():
    events = [AdverseEvent(term=f"R{n}", count=50 - n, serious=False) for n in range(15)]
    evidence = AdverseEventEvidence(events=events, total_count=900, query_url=FAERS_URL)
    items = build_faers_items("warfarin", "11289", "warfarin", evidence, 3, RETRIEVED_AT)
    assert [i.section for i in items] == ["faers_reaction"] * 3 + ["faers_total"]


def test_no_faers_reports_gives_absence_item():
    evidence = AdverseEventEvidence(events=[], total_count=0, query_url=FAERS_URL)
    items = build_faers_items("Zorvax", "1", "zorvax", evidence, 10, RETRIEVED_AT)
    assert len(items) == 1
    assert items[0].source == "absence" and items[0].section == "faers"
    assert items[0].text == "No FAERS reports were found for zorvax as of 2026-10-20."


# --- recall items ---

def test_recall_items_newest_n_with_template():
    evidence = RecallEvidence(recalls=[_record(n) for n in range(5)], total_count=5, query_url=RECALL_URL)
    items = build_recall_items("warfarin", "11289", "warfarin", evidence, 2, RETRIEVED_AT)
    assert [i.text.split(":")[0] for i in items] == [
        "FDA enforcement record D-0000-2026", "FDA enforcement record D-0001-2026",
    ]
    assert items[0].text == (
        "FDA enforcement record D-0000-2026: Class II, initiated 2026-09-30, status Ongoing. "
        "Reason: Failed dissolution specifications. Product: Warfarin Sodium Tablets, 5 mg "
        "Note: matched on ingredient name; confirm the specific product."
    )
    for item in items:
        assert item.source == "openfda_recall" and item.section == "recalls"
        assert item.url == RECALL_URL and item.ingredient == "warfarin"


def test_long_recall_text_shortened_at_word_boundary():
    reason = " ".join(f"reasonword{n}" for n in range(60))
    product = " ".join(f"productword{n}" for n in range(40))
    evidence = RecallEvidence(recalls=[_record(0, reason, product)], total_count=1, query_url=RECALL_URL)
    text = build_recall_items("warfarin", "11289", "warfarin", evidence, 3, RETRIEVED_AT)[0].text
    assert len(text) <= MAX_CHUNK_CHARS
    assert text.count(ELLIPSIS) == 2
    reason_part = text.split("Reason: ")[1].split(" Product: ")[0]
    product_part = text.split(" Product: ")[1].split(" Note: ")[0]
    # Each shortened part is a whole-word prefix of the original.
    assert (reason_part[:-1] + " ") in (reason + " ") and reason.startswith(reason_part[:-1])
    assert (product_part[:-1] + " ") in (product + " ") and product.startswith(product_part[:-1])
    assert text.endswith("Note: matched on ingredient name; confirm the specific product.")


def test_short_product_gives_reason_the_budget():
    reason = " ".join(f"reasonword{n}" for n in range(80))
    evidence = RecallEvidence(recalls=[_record(0, reason, "Warfarin 5 mg")], total_count=1, query_url=RECALL_URL)
    text = build_recall_items("warfarin", "11289", "warfarin", evidence, 3, RETRIEVED_AT)[0].text
    assert len(text) <= MAX_CHUNK_CHARS and "Product: Warfarin 5 mg Note:" in text
    assert text.count(ELLIPSIS) == 1


def test_no_recalls_gives_absence_item():
    evidence = RecallEvidence(recalls=[], total_count=0, query_url=RECALL_URL)
    items = build_recall_items("warfarin", "11289", "warfarin", evidence, 3, RETRIEVED_AT)
    assert [(i.source, i.section) for i in items] == [("absence", "recalls")]
    assert items[0].text == "No FDA enforcement records matched warfarin as of 2026-10-20."


# --- assembly: cap, order, E-IDs ---

def _many_sentences(prefix: str, n: int) -> str:
    # n sentences of exactly 303 chars: two never fit in one 600-char chunk, so n chunks
    return " ".join(f"{prefix[0]}{k:02d} " + "word " * 59 + "end." for k in range(n))


def _full_items() -> list:
    label = _label(
        boxed_warnings=[_many_sentences("Boxed", 4)],
        indications_and_usage=[_many_sentences("Indications", 4)],
        contraindications=[_many_sentences("Contra", 4)],
        precautions=[_many_sentences("Warnings", 20)],
        drug_interactions=[_many_sentences("Interactions", 10)],
        dosage_and_administration=[_many_sentences("Dosage", 10)],
    )
    events = [AdverseEvent(term=f"R{n}", count=50 - n, serious=False) for n in range(10)]
    faers = AdverseEventEvidence(events=events, total_count=900, query_url=FAERS_URL)
    recalls = RecallEvidence(recalls=[], total_count=0, query_url=RECALL_URL)
    # Absence item first on purpose: assembly must move it to the end.
    return (
        build_recall_items("warfarin", "11289", "warfarin", recalls, 2, RETRIEVED_AT)
        + build_label_items("warfarin", "11289", label, list(LABEL_SECTIONS), RETRIEVED_AT)
        + build_faers_items("warfarin", "11289", "warfarin", faers, 3, RETRIEVED_AT)
    )


def test_assembly_caps_and_keeps_faers_recall_absence():
    items = _full_items()
    assert len(items) > MAX_EVIDENCE_ITEMS
    final = assemble_evidence(items)
    assert len(final) == MAX_EVIDENCE_ITEMS
    sources = [i.source for i in final]
    assert sources[-5:] == ["faers"] * 4 + ["absence"]
    assert sources[:-5] == ["dailymed_label"] * (MAX_EVIDENCE_ITEMS - 5)


def test_assembly_round_robin_keeps_first_chunks_of_every_section():
    items = _full_items()
    position = {}
    for item in items:
        if item.source == "dailymed_label":
            position[item.internal_id] = sum(
                1 for p in items[:items.index(item)]
                if p.source == "dailymed_label" and p.section == item.section
            )
    kept: dict[str, list[int]] = {}
    for item in assemble_evidence(items):
        if item.source == "dailymed_label":
            kept.setdefault(item.section, []).append(position[item.internal_id])
    # Section order kept; 15 label slots round-robin over 6 sections: two full
    # rounds (12), then the third round reaches the first 3 sections; first chunks only.
    assert list(kept) == list(LABEL_SECTIONS)
    assert {s: len(v) for s, v in kept.items()} == {
        "boxed_warning": 3, "indications_and_usage": 3, "contraindications": 3,
        "warnings": 2, "drug_interactions": 2, "dosage_and_administration": 2,
    }
    assert all(v == list(range(len(v))) for v in kept.values())


def test_assembly_assigns_sequential_eids_after_ordering():
    final = assemble_evidence(_full_items())
    assert [i.id for i in final] == [f"E{n}" for n in range(1, len(final) + 1)]
    assert len({i.internal_id for i in final}) == len(final)


def test_assembly_under_cap_keeps_everything():
    label = _label(boxed_warnings=["WARNING: BLEEDING RISK Warfarin can cause major or fatal bleeding."])
    items = build_label_items("warfarin", "11289", label, ["boxed_warning", "warnings"], RETRIEVED_AT)
    assert [(i.id, i.source, i.section) for i in assemble_evidence(items)] == [
        ("E1", "dailymed_label", "boxed_warning"), ("E2", "absence", "warnings"),
    ]


def test_assembly_round_robin_across_products():
    a = build_label_items("warfarin", "11289", _label(drug_interactions=[_many_sentences("A", 40)]),
                          ["drug_interactions"], RETRIEVED_AT)
    b = build_label_items("aspirin", "1191", _label(drug_interactions=[_many_sentences("B", 40)]),
                          ["drug_interactions"], RETRIEVED_AT)
    final = assemble_evidence(a + b)
    products = [i.product for i in final]
    assert len(final) == MAX_EVIDENCE_ITEMS
    assert products.count("warfarin") == products.count("aspirin") == MAX_EVIDENCE_ITEMS // 2
