"""
Ten-pair label test (PROJECT.md Section 9.9, CP0 step 0.6).

For each drug pair (A, B), checks whether A's interaction-relevant label sections
name B (ingredient or brand) and vice versa, and records the matching sentence.
The direct-match count decides whether a class layer is needed (7+ pairs: name
matching only).

Pairs with no direct match are also searched for the Section 9.9 class phrases;
hits go under class_mentions and do not affect the count or the decision.

Label choice follows the Section 5.4 title rule. At CP1 this script switches to
the real title-match function in backend/apis/dailymed.py.

Usage:
    .venv/Scripts/python -m benchmark.ten_pair_test

Output:
    benchmark/ten_pair_test.json
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend.apis.rxnorm import fetch_drug_identity

PAIRS: list[tuple[str, str]] = [
    ("warfarin", "aspirin"),
    ("ibuprofen", "lisinopril"),
    ("sertraline", "tramadol"),
    ("simvastatin", "clarithromycin"),
    ("clopidogrel", "omeprazole"),
    ("tizanidine", "ciprofloxacin"),
    ("sildenafil", "nitroglycerin"),
    ("lisinopril", "spironolactone"),
    ("warfarin", "fluconazole"),
    ("digoxin", "amiodarone"),
]

CLASS_PHRASES: list[str] = [
    "NSAIDs",
    "ACE inhibitors",
    "angiotensin receptor blockers",
    "SSRIs",
    "serotonergic drugs",
    "anticoagulants",
    "potassium-sparing diuretics",
    "nitrates",
    "opioids",
    "benzodiazepines",
]

# Section 9.3 sections; warnings uses the Section 6 fallback chain.
SECTION_FIELDS: dict[str, list[str]] = {
    "boxed_warning": ["boxed_warning"],
    "contraindications": ["contraindications"],
    "warnings": [
        "warnings_and_cautions",
        "warnings_and_precautions",
        "warnings",
        "precautions",
    ],
    "drug_interactions": ["drug_interactions"],
}

DIRECT_MATCH_THRESHOLD = 7
MIN_NAME_LENGTH = 4
MAX_SENTENCE_CHARS = 500

_DAILYMED_SPLS_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
_OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
_OUTPUT_PATH = Path(__file__).parent / "ten_pair_test.json"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def select_spl_by_title(spls: list[dict], typed_name: str) -> dict:
    """Section 5.4: first SPL whose title contains the typed name, else first SPL."""
    needle = typed_name.lower()
    for spl in spls:
        if needle in (spl.get("title") or "").lower():
            return spl
    return spls[0]


def match_names(drug: dict) -> list[str]:
    """Section 9.4: ingredients + brand names, lowercased, names under 4 chars dropped."""
    names = {n.lower() for n in drug["ingredients"] + drug["brand_names"]}
    return sorted(n for n in names if len(n) >= MIN_NAME_LENGTH)


def find_mentions(sections: dict[str, list[str]], terms: list[str]) -> list[dict]:
    """Every sentence in the sections that contains a term as a whole word."""
    mentions = []
    for section, texts in sections.items():
        for text in texts:
            for sentence in _SENTENCE_SPLIT.split(text):
                for term in terms:
                    if re.search(rf"\b{re.escape(term)}\b", sentence, re.IGNORECASE):
                        mentions.append({
                            "section": section,
                            "term": term,
                            "sentence": sentence.strip()[:MAX_SENTENCE_CHARS],
                        })
    return mentions


async def fetch_spls(client: httpx.AsyncClient, rxcui: str) -> list[dict]:
    response = await client.get(_DAILYMED_SPLS_URL, params={"rxcui": rxcui})
    response.raise_for_status()
    return response.json().get("data", [])


async def fetch_openfda_label(client: httpx.AsyncClient, set_id: str) -> dict:
    response = await client.get(
        _OPENFDA_LABEL_URL, params={"search": f'set_id:"{set_id}"', "limit": 1}
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    return results[0] if results else {}


def extract_sections(label: dict) -> tuple[dict[str, list[str]], dict[str, str | None]]:
    sections: dict[str, list[str]] = {}
    source_fields: dict[str, str | None] = {}
    for section, fields in SECTION_FIELDS.items():
        sections[section] = []
        source_fields[section] = None
        for field in fields:
            value = label.get(field)
            if value:
                sections[section] = value if isinstance(value, list) else [value]
                source_fields[section] = field
                break
    return sections, source_fields


async def load_drug(client: httpx.AsyncClient, name: str) -> dict:
    identity = await fetch_drug_identity(name)
    drug = {
        "input_name": name,
        "rxcui": identity.rxcui,
        "preferred_name": identity.normalized_name,
        # v1 keeps only the first ingredient; all 20 names here are single-ingredient.
        "ingredients": [identity.generic_name] if identity.generic_name else [],
        "brand_names": identity.brand_names,
        "label": None,
        "sections_present": {},
        "error": None,
    }
    try:
        spls = await fetch_spls(client, identity.rxcui)
        if not spls:
            drug["error"] = "no DailyMed SPLs for rxcui"
            drug["sections"] = {}
            return drug
        spl = select_spl_by_title(spls, name)
        label = await fetch_openfda_label(client, spl["setid"])
    except httpx.HTTPError as exc:
        drug["error"] = f"{type(exc).__name__}: {exc}"
        drug["sections"] = {}
        return drug

    sections, source_fields = extract_sections(label)
    drug["label"] = {
        "title": spl.get("title"),
        "set_id": spl.get("setid"),
        "dailymed_published_date": spl.get("published_date"),
        "openfda_effective_time": label.get("effective_time"),
        "spl_count_on_page": len(spls),
        "title_matched": name.lower() in (spl.get("title") or "").lower(),
        "openfda_found": bool(label),
    }
    drug["sections_present"] = {s: source_fields[s] for s in SECTION_FIELDS}
    drug["sections"] = sections
    return drug


def evaluate_pair(a: dict, b: dict) -> dict:
    a_matches = find_mentions(a["sections"], match_names(b))
    b_matches = find_mentions(b["sections"], match_names(a))
    direct = bool(a_matches or b_matches)
    result = {
        "pair": [a["input_name"], b["input_name"]],
        "a_names_b": bool(a_matches),
        "b_names_a": bool(b_matches),
        "direct_match": direct,
        "a_matches": a_matches,
        "b_matches": b_matches,
        "class_mentions": None,
    }
    if not direct:
        result["class_mentions"] = {
            a["input_name"]: find_mentions(a["sections"], CLASS_PHRASES),
            b["input_name"]: find_mentions(b["sections"], CLASS_PHRASES),
        }
    return result


def drug_record(drug: dict) -> dict:
    return {k: v for k, v in drug.items() if k != "sections"}


async def main() -> None:
    names = sorted({n for pair in PAIRS for n in pair})
    async with httpx.AsyncClient(timeout=20.0) as client:
        loaded = await asyncio.gather(*(load_drug(client, n) for n in names))
    drugs = dict(zip(names, loaded))

    pairs = [evaluate_pair(drugs[a], drugs[b]) for a, b in PAIRS]
    direct_count = sum(p["direct_match"] for p in pairs)
    decision = (
        "name matching only"
        if direct_count >= DIRECT_MATCH_THRESHOLD
        else "add class layer (RxClass + class phrase table)"
    )

    output = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "pairs": len(pairs),
            "direct_match_count": direct_count,
            "threshold": DIRECT_MATCH_THRESHOLD,
            "decision": decision,
        },
        "drugs": {n: drug_record(d) for n, d in drugs.items()},
        "pairs": pairs,
    }
    _OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(output["summary"], indent=2))
    for p in pairs:
        print(
            f"{p['pair'][0]} + {p['pair'][1]}: "
            f"A->B={p['a_names_b']} B->A={p['b_names_a']} direct={p['direct_match']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
