"""
Integrity checks for benchmark/questions.jsonl against the frozen label snapshot
(PROJECT.md Section 13). Pure: reads two local files, no network.

benchmark/ is gitignored and local-only, so the module skips when it is absent.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

BENCHMARK = Path(__file__).resolve().parent.parent / "benchmark"
if not (BENCHMARK / "questions.jsonl").is_file() or not (BENCHMARK / "label_snapshot.json").is_file():
    pytest.skip("benchmark/ is local-only and not present", allow_module_level=True)

QUESTIONS = [
    json.loads(line)
    for line in (BENCHMARK / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
SNAPSHOT = json.loads((BENCHMARK / "label_snapshot.json").read_text(encoding="utf-8"))["drugs"]

FIELDS = {
    "id", "type", "question", "drug", "answerable", "expected_behavior",
    "answer_key", "key_passage", "label_set_id", "drafted_by",
}
EXPECTED_MIX = {
    "boxed_warning": 6, "contraindications": 6, "warnings": 6, "interactions": 6,
    "indications": 3, "dosing": 3,
    "trick_made_up": 2, "trick_not_in_label": 2, "trick_personal_advice": 1,
}
TYPE_TO_SECTION = {
    "boxed_warning": "boxed_warning",
    "contraindications": "contraindications",
    "warnings": "warnings",
    "interactions": "drug_interactions",
    "indications": "indications_and_usage",
    "dosing": "dosage_and_administration",
}
BENCHMARK_DRUGS = {
    "warfarin", "metformin", "lisinopril", "atorvastatin", "sertraline", "ibuprofen",
    "acetaminophen", "amoxicillin", "levothyroxine", "Ozempic", "clopidogrel",
    "prednisone", "tramadol", "amlodipine", "omeprazole",
}
BEHAVIORS = {"answer", "not_recognized", "insufficient", "block"}
DRAFTED_BY = {"claude_code", "claude_code, edited by owner"}
LABEL_ITEMS = [q for q in QUESTIONS if q["type"] in TYPE_TO_SECTION]


def normalize(text: str) -> str:
    """PROJECT.md Section 8 L1 normalization."""
    text = text.lower()
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def test_counts_and_mix():
    assert len(QUESTIONS) == 35
    assert Counter(q["type"] for q in QUESTIONS) == EXPECTED_MIX


def test_ids_unique():
    assert len({q["id"] for q in QUESTIONS}) == len(QUESTIONS)


@pytest.mark.parametrize("q", QUESTIONS, ids=lambda q: q["id"])
def test_fields_and_values(q):
    assert set(q) == FIELDS
    assert q["expected_behavior"] in BEHAVIORS
    assert q["drafted_by"] in DRAFTED_BY
    assert q["question"].strip()


@pytest.mark.parametrize("q", LABEL_ITEMS, ids=lambda q: q["id"])
def test_label_item_traces_to_snapshot(q):
    assert q["drug"] in BENCHMARK_DRUGS
    assert q["answerable"] is True and q["expected_behavior"] == "answer"
    label = SNAPSHOT[q["drug"]]["label"]
    assert q["label_set_id"] == label["set_id"]
    section_text = normalize(" ".join(label["sections"][TYPE_TO_SECTION[q["type"]]]))
    assert normalize(q["key_passage"]) in section_text, "key_passage is not verbatim label text"
    assert normalize(q["answer_key"]) in normalize(q["key_passage"]), "answer_key is not inside key_passage"


@pytest.mark.parametrize("q", LABEL_ITEMS, ids=lambda q: q["id"])
def test_question_does_not_copy_label_wording(q):
    """Condition 1: the question must not reuse a long run of label words."""
    words = normalize(q["key_passage"]).split()
    question = normalize(q["question"])
    for i in range(len(words) - 5):
        assert " ".join(words[i:i + 6]) not in question


def test_trick_items():
    tricks = [q for q in QUESTIONS if q["type"].startswith("trick_")]
    for q in tricks:
        assert q["answerable"] is False
        assert q["key_passage"] == ""
    made_up = [q for q in tricks if q["type"] == "trick_made_up"]
    assert all(q["drug"] not in SNAPSHOT and q["expected_behavior"] == "not_recognized" for q in made_up)
    for q in (q for q in tricks if q["type"] == "trick_not_in_label"):
        assert q["drug"] in BENCHMARK_DRUGS and q["expected_behavior"] == "insufficient"
        assert q["label_set_id"] == SNAPSHOT[q["drug"]]["label"]["set_id"]
    advice = [q for q in tricks if q["type"] == "trick_personal_advice"]
    assert all(q["expected_behavior"] == "block" for q in advice)
