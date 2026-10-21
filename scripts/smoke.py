"""
Smoke checks with real network calls (PROJECT.md Section 15). Run by hand at the
end of each checkpoint; raw results are printed.

Checks are grouped by checkpoint. CP1 RxNorm checks call fetch_drug_identity
directly so they exercise RxNorm alone, without the LLM stages in /investigate.

Usage:
    .venv/Scripts/python -m scripts.smoke
"""

import asyncio
import json
import sys

from backend.apis.dailymed import fetch_label_evidence
from backend.apis.rxnorm import RxNormDrugNotFoundError, fetch_drug_identity


async def check_rxnorm_resolves(drug_name: str, expected_rxcui: str, expected_name: str) -> bool:
    identity = await fetch_drug_identity(drug_name)
    print(json.dumps(identity.model_dump(), indent=2))
    return identity.rxcui == expected_rxcui and identity.normalized_name.lower() == expected_name


async def check_rxnorm_not_found(drug_name: str) -> bool:
    try:
        identity = await fetch_drug_identity(drug_name)
    except RxNormDrugNotFoundError as exc:
        print(f"RxNormDrugNotFoundError: {exc}")
        return True
    print(json.dumps(identity.model_dump(), indent=2))
    return False


async def check_rxnorm_brands(drug_name: str, required: set[str], excluded: set[str]) -> bool:
    identity = await fetch_drug_identity(drug_name)
    print(json.dumps(identity.model_dump(), indent=2))
    brands = set(identity.brand_names)
    return required <= brands and not (excluded & brands)


async def check_rxnorm_ingredients(drug_name: str, expected: set[str]) -> bool:
    identity = await fetch_drug_identity(drug_name)
    print(json.dumps(identity.model_dump(), indent=2))
    return {name.lower() for name in identity.ingredients} == expected


async def check_label(
    drug_name: str, title_excludes: str | None = None,
    title_includes: str | None = None, set_id: str | None = None,
) -> bool:
    identity = await fetch_drug_identity(drug_name)
    label = await fetch_label_evidence(
        identity.rxcui, identity.input_name, len(identity.ingredients) == 1
    )
    summary = label.model_dump(include={
        "label_title", "set_id", "effective_date", "url", "tie_breaker", "skipped_set_ids",
    })
    summary["section_counts"] = {
        name: len(getattr(label, name)) for name in (
            "boxed_warnings", "indications_and_usage", "dosage_and_administration",
            "contraindications", "precautions", "drug_interactions",
        )
    }
    print(json.dumps(summary, indent=2))
    title = label.label_title.upper()
    return (
        (title_excludes is None or title_excludes not in title)
        and (title_includes is None or title_includes in title)
        and (set_id is None or label.set_id == set_id)
        and bool(label.indications_and_usage)
    )


CHECKS = [
    ("cp1 rxnorm: 'omeprazole' -> omeprazole, not esomeprazole",
     lambda: check_rxnorm_resolves("omeprazole", "7646", "omeprazole")),
    ("cp1 rxnorm: 'warfrin' does not resolve",
     lambda: check_rxnorm_not_found("warfrin")),
    ("cp1 rxnorm: 'Zorvaxitran' does not resolve",
     lambda: check_rxnorm_not_found("Zorvaxitran")),
    ("cp1 rxnorm: 'Warfarin' resolves to warfarin",
     lambda: check_rxnorm_resolves("Warfarin", "11289", "warfarin")),
    ("cp1 rxnorm: omeprazole brands keep Prilosec, exclude combination brands",
     lambda: check_rxnorm_brands(
         "omeprazole",
         required={"Prilosec"},
         excluded={"Yosprala", "Talicia", "Konvomep", "Zegerid Reformulated Aug 2006"},
     )),
    ("cp1 rxnorm: 'Tylenol PM' -> acetaminophen + diphenhydramine",
     lambda: check_rxnorm_ingredients("Tylenol PM", {"acetaminophen", "diphenhydramine"})),
    ("cp1 label: omeprazole does not pick an esomeprazole label",
     lambda: check_label("omeprazole", title_excludes="ESOMEPRAZOLE")),
    ("cp1 label: digoxin does not pick DIGIFAB",
     lambda: check_label("digoxin", title_excludes="DIGIFAB")),
    ("cp1 label: tramadol does not pick the tramadol + acetaminophen combination",
     lambda: check_label("tramadol", title_excludes="ACETAMINOPHEN")),
    ("cp1 label: Ozempic picks the injection label",
     lambda: check_label(
         "Ozempic", title_includes="INJECTION",
         set_id="42bdd912-2393-44c4-b7e0-47672ca28991",
     )),
]


async def main() -> int:
    failures = 0
    for label, run in CHECKS:
        print(f"\n=== {label}")
        passed = await run()
        print("PASS" if passed else "FAIL")
        failures += not passed
    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
