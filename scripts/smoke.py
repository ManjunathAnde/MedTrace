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


CHECKS = [
    ("cp1 rxnorm: 'omeprazole' -> omeprazole, not esomeprazole",
     lambda: check_rxnorm_resolves("omeprazole", "7646", "omeprazole")),
    ("cp1 rxnorm: 'warfrin' does not resolve",
     lambda: check_rxnorm_not_found("warfrin")),
    ("cp1 rxnorm: 'Zorvaxitran' does not resolve",
     lambda: check_rxnorm_not_found("Zorvaxitran")),
    ("cp1 rxnorm: 'Warfarin' resolves to warfarin",
     lambda: check_rxnorm_resolves("Warfarin", "11289", "warfarin")),
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
