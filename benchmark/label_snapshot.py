"""
Frozen label snapshot for the benchmark (PROJECT.md Section 13, CP0 step 0.7).

For each of the 15 benchmark drugs, resolves the name the way v2 will
(Section 5.3: prefer the RxNorm candidate whose name equals the input) and
selects the label the way v2 will (Section 5.4 ordered tie-breakers, skipping
SPLs whose set ID is missing from openFDA). Saves the six Section 6 label
sections so answer keys and the CP7 judge use the same frozen text.

Both rules are duplicated here until CP1, when this script switches to the real
functions in backend/apis/.

Usage:
    .venv/Scripts/python -m benchmark.label_snapshot

Output:
    benchmark/label_snapshot.json
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("label_snapshot")

# Names as they appear in benchmark questions (semaglutide is asked as Ozempic).
DRUGS: list[str] = [
    "warfarin",
    "metformin",
    "lisinopril",
    "atorvastatin",
    "sertraline",
    "ibuprofen",
    "acetaminophen",
    "amoxicillin",
    "levothyroxine",
    "Ozempic",
    "clopidogrel",
    "prednisone",
    "tramadol",
    "amlodipine",
    "omeprazole",
]

# Section 6 sections; warnings uses the fallback chain, stored as "warnings".
SECTION_FIELDS: dict[str, list[str]] = {
    "boxed_warning": ["boxed_warning"],
    "indications_and_usage": ["indications_and_usage"],
    "dosage_and_administration": ["dosage_and_administration"],
    "contraindications": ["contraindications"],
    "warnings": [
        "warnings_and_cautions",
        "warnings_and_precautions",
        "warnings",
        "precautions",
    ],
    "drug_interactions": ["drug_interactions"],
}

_RXNAV_URL = "https://rxnav.nlm.nih.gov/REST"
_DAILYMED_SPLS_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
_OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
_OUTPUT_PATH = Path(__file__).parent / "label_snapshot.json"


async def _rxnorm_name(client: httpx.AsyncClient, rxcui: str) -> tuple[str | None, str | None]:
    response = await client.get(f"{_RXNAV_URL}/rxcui/{rxcui}/properties.json")
    response.raise_for_status()
    props = response.json().get("properties", {})
    return props.get("name"), props.get("tty")


async def _related_names(client: httpx.AsyncClient, rxcui: str, tty: str) -> list[str]:
    response = await client.get(f"{_RXNAV_URL}/rxcui/{rxcui}/related.json", params={"tty": tty})
    response.raise_for_status()
    groups = response.json().get("relatedGroup", {}).get("conceptGroup", [])
    return [c["name"] for g in groups for c in g.get("conceptProperties", []) if c.get("name")]


async def resolve_drug(client: httpx.AsyncClient, name: str) -> dict:
    """Section 5.3: prefer the candidate whose name equals the input; else v1 behavior."""
    response = await client.get(f"{_RXNAV_URL}/rxcui.json", params={"name": name, "search": 1})
    response.raise_for_status()
    candidates = response.json().get("idGroup", {}).get("rxnormId") or []
    if not candidates:
        return {"input_name": name, "rxcui": None, "resolution_rule": "not_found"}

    props = {c: await _rxnorm_name(client, c) for c in candidates}
    exact = [c for c in candidates if (props[c][0] or "").lower() == name.lower()]
    if exact:
        rxcui, rule = exact[0], "exact_name"
    else:
        ingredient = [c for c in candidates if props[c][1] == "IN"]
        rxcui, rule = (ingredient[0], "first_IN") if ingredient else (candidates[0], "first")

    return {
        "input_name": name,
        "rxcui": rxcui,
        "preferred_name": props[rxcui][0],
        "resolution_rule": rule,
        "candidates": {c: props[c][0] for c in candidates},
        "ingredients": await _related_names(client, rxcui, "IN"),
        "brand_names": await _related_names(client, rxcui, "BN"),
    }


def title_tier(title: str, typed_name: str, single_ingredient: bool) -> int:
    """Section 5.4 tie-breakers: 1 (best) to 4 (first SPL fallback)."""
    word = rf"{re.escape(typed_name)}\b"
    starts = re.match(word, title, re.IGNORECASE) is not None
    is_combination = " AND " in title.upper()
    if starts and not (single_ingredient and is_combination):
        return 1
    if starts:
        return 2
    if re.search(rf"\b{word}", title, re.IGNORECASE):
        return 3
    return 4


def order_spls(spls: list[dict], typed_name: str, single_ingredient: bool) -> list[tuple[int, dict]]:
    """Stable sort by tier, so page order breaks ties within a tier."""
    tiers = [(title_tier(s.get("title") or "", typed_name, single_ingredient), s) for s in spls]
    return sorted(tiers, key=lambda t: t[0])


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


async def select_label(client: httpx.AsyncClient, drug: dict) -> dict:
    response = await client.get(_DAILYMED_SPLS_URL, params={"rxcui": drug["rxcui"]})
    response.raise_for_status()
    spls = response.json().get("data", [])
    single = len(drug["ingredients"]) == 1
    skipped = []
    for tier, spl in order_spls(spls, drug["input_name"], single):
        r = await client.get(
            _OPENFDA_LABEL_URL, params={"search": f'set_id:"{spl["setid"]}"', "limit": 1}
        )
        if r.status_code == 404 or (r.status_code == 200 and not r.json().get("results")):
            logger.info("skip %s: set_id %s not in openFDA (%s)", drug["input_name"], spl["setid"], spl.get("title"))
            skipped.append(spl["setid"])
            continue
        r.raise_for_status()
        label = r.json()["results"][0]
        sections, source_fields = extract_sections(label)
        return {
            "title": spl.get("title"),
            "set_id": spl["setid"],
            "dailymed_published_date": spl.get("published_date"),
            "openfda_effective_time": label.get("effective_time"),
            "url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={spl['setid']}",
            "tie_breaker": tier,
            "skipped_set_ids": skipped,
            "spl_count_on_page": len(spls),
            "section_source_fields": source_fields,
            "sections": sections,
        }
    return {"error": "no SPL on page 1 has an openFDA label", "skipped_set_ids": skipped}


async def snapshot_drug(client: httpx.AsyncClient, name: str) -> dict:
    drug = await resolve_drug(client, name)
    if drug["rxcui"] is None:
        return drug
    drug["label"] = await select_label(client, drug)
    return drug


async def main() -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        results = await asyncio.gather(*(snapshot_drug(client, n) for n in DRUGS))
    output = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "drugs": {d["input_name"]: d for d in results},
    }
    _OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    for d in results:
        label = d.get("label") or {}
        present = [s for s, f in (label.get("section_source_fields") or {}).items() if f]
        print(
            f"{d['input_name']}: rxcui={d.get('rxcui')} ({d.get('resolution_rule')}, {d.get('preferred_name')}) "
            f"ingredients={d.get('ingredients')} tier={label.get('tie_breaker')} "
            f"skipped={len(label.get('skipped_set_ids', []))}\n"
            f"    {label.get('title')!r} set_id={label.get('set_id')} eff={label.get('openfda_effective_time')}\n"
            f"    sections: {present}"
        )


if __name__ == "__main__":
    asyncio.run(main())
