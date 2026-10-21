"""
Evidence store (PROJECT.md Section 6).

Turns retrieved API data into EvidenceItems: the only text the LLM sees.
Everything here is pure and deterministic; no network or LLM calls.
"""

import hashlib
import re

from backend.models.evidence import (
    AdverseEventEvidence,
    EvidenceItem,
    EvidenceSource,
    LabelEvidence,
)

MAX_CHUNK_CHARS = 600
MIN_CHUNK_CHARS = 20
FAERS_TOP_REACTIONS = 10

# Section 6 label sections, in evidence order.
LABEL_SECTIONS: tuple[str, ...] = (
    "boxed_warning",
    "indications_and_usage",
    "contraindications",
    "warnings",
    "drug_interactions",
    "dosage_and_administration",
)

# Section name -> LabelEvidence field (warnings is stored as precautions until
# the profile rebuild).
_LABEL_FIELDS: dict[str, str] = {
    "boxed_warning": "boxed_warnings",
    "indications_and_usage": "indications_and_usage",
    "contraindications": "contraindications",
    "warnings": "precautions",
    "drug_interactions": "drug_interactions",
    "dosage_and_administration": "dosage_and_administration",
}

SECTION_HUMAN: dict[str, str] = {
    "boxed_warning": "boxed warning",
    "indications_and_usage": "indications and usage",
    "dosage_and_administration": "dosage and administration",
    "contraindications": "contraindications",
    "warnings": "warnings",
    "drug_interactions": "drug interactions",
}

_FAERS_DISCLAIMER = "FAERS reports do not establish that the drug caused the event."

# Each section's own heading, as openFDA repeats it at the start of the text
# ("4 CONTRAINDICATIONS ...", "5 WARNINGS AND PRECAUTIONS ..."). Boxed warnings
# keep their "WARNING: ..." title: it names the risk.
_SECTION_HEADINGS: dict[str, str] = {
    "boxed_warning": r"BOXED WARNING",
    "indications_and_usage": r"INDICATIONS (?:AND|&) USAGE",
    "dosage_and_administration": r"DOSAGE (?:AND|&) ADMINISTRATION",
    "contraindications": r"CONTRAINDICATIONS",
    "warnings": r"WARNINGS (?:AND|&) (?:PRECAUTIONS|CAUTIONS)|WARNINGS|PRECAUTIONS",
    "drug_interactions": r"DRUG INTERACTIONS",
}

_LEADING_NUMBER = r"\d+(?:\.\d+)*\s+(?=[A-Za-z])"
_BLANK_LINES = re.compile(r"\n\s*\n")
_SENTENCE_BOUNDARY = re.compile(r"(?<=\.)\s+(?=[A-Z])")
_BULLET_BOUNDARY = re.compile(r"\s*(?=•)")
_SEMICOLON_BOUNDARY = re.compile(r"(?<=;)\s+")
# Fallbacks for a single sentence over the limit, tried in order (Section 6).
_LONG_SENTENCE_BOUNDARIES = (_BULLET_BOUNDARY, _SEMICOLON_BOUNDARY)


def strip_section_heading(text: str, section: str) -> str:
    """Remove a leading section number and the section's own heading, if present."""
    heading = _SECTION_HEADINGS.get(section)
    pattern = rf"^\s*(?:{_LEADING_NUMBER})?"
    if heading:
        pattern += rf"(?:(?:{heading})\b:?\s*)?"
    return re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_on(text: str, start: int, end: int, boundary: re.Pattern) -> list[tuple[int, int]]:
    spans = []
    piece_start = start
    for match in boundary.finditer(text, start, end):
        spans.append(_trim(text, piece_start, match.start()))
        piece_start = match.end()
    spans.append(_trim(text, piece_start, end))
    return [(s, e) for s, e in spans if e > s]


def _split_at_spaces(text: str, start: int, end: int) -> list[tuple[int, int]]:
    # Last resort: cut at the last space before the limit, never mid-word.
    spans = []
    while end - start > MAX_CHUNK_CHARS:
        cut = text.rfind(" ", start, start + MAX_CHUNK_CHARS + 1)
        if cut <= start:
            cut = start + MAX_CHUNK_CHARS  # a single "word" over the limit
        spans.append(_trim(text, start, cut))
        start, end = _trim(text, cut, end)
    spans.append((start, end))
    return [(s, e) for s, e in spans if e > s]


def _split_long(
    text: str, start: int, end: int, boundaries: tuple[re.Pattern, ...]
) -> list[tuple[int, int]]:
    if end - start <= MAX_CHUNK_CHARS:
        return [(start, end)]
    if not boundaries:
        return _split_at_spaces(text, start, end)
    pieces = _split_on(text, start, end, boundaries[0])
    spans = []
    for s, e in pieces:
        spans.extend(_split_long(text, s, e, boundaries[1:]))
    return spans


def _pack(text: str, spans: list[tuple[int, int]]) -> list[str]:
    # Join neighbouring spans while the joined text stays within the limit.
    chunks = []
    current: tuple[int, int] | None = None
    for s, e in spans:
        if current is None:
            current = (s, e)
        elif e - current[0] <= MAX_CHUNK_CHARS:
            current = (current[0], e)
        else:
            chunks.append(text[current[0]:current[1]])
            current = (s, e)
    if current is not None:
        chunks.append(text[current[0]:current[1]])
    return chunks


def chunk_section_text(text: str, section: str) -> list[str]:
    """
    Split one openFDA section string into chunks (PROJECT.md Section 6):
    strip the leading heading, split on blank lines, split pieces over
    MAX_CHUNK_CHARS at sentence boundaries, split a single over-long sentence at
    bullets, then "; ", then the last space; drop chunks under MIN_CHUNK_CHARS.
    Every chunk is a verbatim substring of the input.
    """
    body = strip_section_heading(text, section)
    chunks = []
    for start, end in _split_on(body, 0, len(body), _BLANK_LINES):
        spans = []
        for s, e in _split_on(body, start, end, _SENTENCE_BOUNDARY):
            spans.extend(_split_long(body, s, e, _LONG_SENTENCE_BOUNDARIES))
        chunks.extend(_pack(body, spans))
    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


def make_internal_id(
    source: EvidenceSource, set_id: str | None, section: str, chunk_index: int, text: str
) -> str:
    """sha1(source|set_id|section|chunk_index|text)[:12]; same input, same id."""
    key = "|".join((source, set_id or "", section, str(chunk_index), text))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _item(
    *,
    product: str,
    rxcui: str,
    source: EvidenceSource,
    section: str,
    chunk_index: int,
    text: str,
    url: str,
    retrieved_at: str,
    ingredient: str | None = None,
    label: LabelEvidence | None = None,
) -> EvidenceItem:
    set_id = label.set_id if label else None
    return EvidenceItem(
        id="",
        internal_id=make_internal_id(source, set_id, section, chunk_index, text),
        product=product,
        ingredient=ingredient,
        rxcui=rxcui,
        source=source,
        section=section,
        text=text,
        url=url,
        label_title=label.label_title if label else None,
        label_set_id=set_id,
        label_effective_date=label.effective_date if label else None,
        retrieved_at=retrieved_at,
    )


def build_label_items(
    product: str,
    rxcui: str,
    label: LabelEvidence,
    sections: list[str],
    retrieved_at: str,
) -> list[EvidenceItem]:
    """
    Chunk the requested label sections into items, in Section 6 order. A
    requested section with no text gets one absence item instead.
    """
    items = []
    for section in (s for s in LABEL_SECTIONS if s in sections):
        chunks = [
            chunk
            for text in getattr(label, _LABEL_FIELDS[section])
            for chunk in chunk_section_text(text, section)
        ]
        if not chunks:
            items.append(_item(
                product=product, rxcui=rxcui, source="absence", section=section,
                chunk_index=0, url=label.url, retrieved_at=retrieved_at, label=label,
                text=(
                    f"The retrieved {product} label ({label.label_title}, set ID "
                    f"{label.set_id}) contains no {SECTION_HUMAN[section]} section."
                ),
            ))
            continue
        for index, chunk in enumerate(chunks):
            items.append(_item(
                product=product, rxcui=rxcui, source="dailymed_label", section=section,
                chunk_index=index, text=chunk, url=label.url,
                retrieved_at=retrieved_at, label=label,
            ))
    return items


def build_faers_items(
    product: str,
    rxcui: str,
    ingredient: str,
    evidence: AdverseEventEvidence,
    url: str,
    retrieved_at: str,
) -> list[EvidenceItem]:
    """
    Code-written FAERS items for one ingredient: top reactions plus the total,
    each with the causation disclaimer; one absence item when there are none.
    `url` is the openFDA query URL.
    """
    date = retrieved_at[:10]
    common = dict(
        product=product, rxcui=rxcui, ingredient=ingredient, url=url, retrieved_at=retrieved_at,
    )
    if not evidence.events and evidence.total_count == 0:
        return [_item(
            **common, source="absence", section="faers", chunk_index=0,
            text=f"No FAERS reports were found for {ingredient} as of {date}.",
        )]
    items = [
        _item(
            **common, source="faers", section="faers_reaction", chunk_index=index,
            text=(
                f"FAERS: {event.count} reports list '{event.term}' for {ingredient} "
                f"(retrieved {date}). {_FAERS_DISCLAIMER}"
            ),
        )
        for index, event in enumerate(evidence.events[:FAERS_TOP_REACTIONS])
    ]
    items.append(_item(
        **common, source="faers", section="faers_total", chunk_index=0,
        text=(
            f"FAERS: {evidence.total_count} total reports mention {ingredient} "
            f"(retrieved {date}). {_FAERS_DISCLAIMER}"
        ),
    ))
    return items
