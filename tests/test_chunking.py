"""Chunking rules (PROJECT.md §6): chunk_section_text and strip_section_heading."""

import re

from backend.evidence.store import (
    MAX_CHUNK_CHARS,
    chunk_section_text,
    strip_section_heading,
)

BULLET = "•"


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _sentence(n: int, length: int = 100) -> str:
    # One sentence of roughly `length` chars, starting uppercase, ending ". "
    words = f"Sentence {n} says"
    filler = " word" * ((length - len(words) - 1) // 5)
    return f"{words}{filler}."


def test_strips_number_and_own_heading():
    text = "4 CONTRAINDICATIONS Warfarin sodium tablets are contraindicated in pregnancy."
    assert strip_section_heading(text, "contraindications").startswith("Warfarin sodium")
    text = "5 WARNINGS AND PRECAUTIONS 5.1 Hemorrhage Warfarin can cause major bleeding."
    assert strip_section_heading(text, "warnings") == "5.1 Hemorrhage Warfarin can cause major bleeding."
    text = "1 INDICATIONS & USAGE Lisinopril is indicated for hypertension."
    assert strip_section_heading(text, "indications_and_usage").startswith("Lisinopril")


def test_strips_leading_subsection_number_only():
    text = "5.1 Risk of Thyroid C-Cell Tumors In mice and rats, semaglutide caused tumors."
    assert strip_section_heading(text, "warnings").startswith("Risk of Thyroid")


def test_keeps_boxed_warning_title_and_other_sections_headings():
    text = "WARNING: BLEEDING RISK Warfarin can cause major or fatal bleeding."
    assert strip_section_heading(text, "boxed_warning") == text
    # Another section's heading is content, not this section's heading.
    text = "DRUG INTERACTIONS are listed in section 7 of this label."
    assert strip_section_heading(text, "contraindications") == text


def test_short_text_is_one_chunk():
    text = "4 CONTRAINDICATIONS Pregnancy. Hemorrhagic tendencies or blood dyscrasias."
    assert chunk_section_text(text, "contraindications") == [
        "Pregnancy. Hemorrhagic tendencies or blood dyscrasias."
    ]


def test_long_text_splits_at_sentence_boundaries_within_limit():
    sentences = [_sentence(i, 150) for i in range(12)]
    text = " ".join(sentences)
    chunks = chunk_section_text(text, "warnings")
    assert len(chunks) > 1
    assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
    # Never mid-sentence: every chunk is a run of whole sentences.
    for chunk in chunks:
        assert chunk.startswith("Sentence ") and chunk.endswith(".")
        assert all(part in sentences for part in re.split(r"(?<=\.) (?=[A-Z])", chunk))
    assert _normalized(" ".join(chunks)) == _normalized(text)


def test_blank_lines_split_paragraphs():
    text = "First paragraph sentence here.\n\nSecond paragraph sentence here."
    assert chunk_section_text(text, "warnings") == [
        "First paragraph sentence here.",
        "Second paragraph sentence here.",
    ]


def test_long_sentence_splits_at_bullets():
    items = [f"{BULLET} Condition number {i} with some descriptive words" for i in range(30)]
    text = "Contraindicated in patients with: " + " ".join(items)
    chunks = chunk_section_text(text, "contraindications")
    assert len(chunks) > 1
    assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
    assert all(c.startswith(BULLET) for c in chunks[1:])
    assert _normalized(" ".join(chunks)) == _normalized(text)


def test_long_sentence_without_bullets_splits_at_semicolons():
    clauses = [f"clause {i} has several more words in it" for i in range(30)]
    text = "Table: " + "; ".join(clauses)
    chunks = chunk_section_text(text, "drug_interactions")
    assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
    assert all(c.endswith(";") for c in chunks[:-1])
    assert _normalized(" ".join(chunks)) == _normalized(text)


def test_last_resort_splits_at_space_never_mid_word():
    words = [f"word{i}" for i in range(200)]
    text = "Table " + " ".join(words)
    chunks = chunk_section_text(text, "drug_interactions")
    assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
    assert " ".join(chunks).split() == text.split()


def test_chunks_under_20_chars_dropped():
    text = "Too short.\n\nThis paragraph is long enough to keep."
    assert chunk_section_text(text, "warnings") == ["This paragraph is long enough to keep."]


def test_chunks_are_verbatim_substrings():
    text = "7 DRUG INTERACTIONS " + " ".join(_sentence(i, 130) for i in range(10))
    body = strip_section_heading(text, "drug_interactions")
    assert all(chunk in body for chunk in chunk_section_text(text, "drug_interactions"))
