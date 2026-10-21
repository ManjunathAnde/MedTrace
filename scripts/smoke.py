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
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from pydantic import BaseModel

from backend.apis.dailymed import fetch_label_evidence
from backend.apis.fda_recall import fetch_recall_evidence
from backend.apis.openfda import fetch_adverse_event_evidence
from backend.apis.rxnorm import RxNormDrugNotFoundError, fetch_drug_identity
from backend.evidence.store import (
    FAERS_TOP_REACTIONS_FULL,
    LABEL_SECTIONS,
    MAX_CHUNK_CHARS,
    MAX_EVIDENCE_ITEMS,
    RECALLS_FULL,
    assemble_evidence,
    build_faers_items,
    build_label_items,
    build_recall_items,
)
from backend.llm.providers import ProvidersUnavailableError, complete_json

FAERS_DISCLAIMER = "FAERS reports do not establish that the drug caused the event."


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


def _item_problems(item) -> list[str]:
    problems = []
    for field in ("id", "internal_id", "product", "rxcui", "source", "section", "text", "url", "retrieved_at"):
        if not getattr(item, field):
            problems.append(f"{item.id}: empty {field}")
    if len(item.text) > MAX_CHUNK_CHARS:
        problems.append(f"{item.id}: text over {MAX_CHUNK_CHARS}")
    if item.source == "dailymed_label" and not (item.label_title and item.label_set_id and item.label_effective_date):
        problems.append(f"{item.id}: label item missing label metadata")
    if item.source in ("faers", "openfda_recall") and not item.ingredient:
        problems.append(f"{item.id}: {item.source} item missing ingredient")
    if item.source == "faers" and not item.text.endswith(FAERS_DISCLAIMER):
        problems.append(f"{item.id}: FAERS item missing disclaimer")
    return problems


async def check_evidence_full(drug_name: str) -> bool:
    """CP2: Full-intent evidence for one drug; every field present, cap and order hold."""
    retrieved_at = datetime.now(timezone.utc).isoformat()
    identity = await fetch_drug_identity(drug_name)
    label = await fetch_label_evidence(
        identity.rxcui, identity.input_name, len(identity.ingredients) == 1
    )
    product = identity.normalized_name
    items = build_label_items(product, identity.rxcui, label, list(LABEL_SECTIONS), retrieved_at)
    for ingredient in identity.ingredients:
        faers = await fetch_adverse_event_evidence(ingredient)
        recalls = await fetch_recall_evidence(ingredient)
        items += build_faers_items(
            product, identity.rxcui, ingredient, faers, FAERS_TOP_REACTIONS_FULL, retrieved_at
        )
        items += build_recall_items(
            product, identity.rxcui, ingredient, recalls, RECALLS_FULL, retrieved_at
        )
    final = assemble_evidence(items)

    problems = [p for item in final for p in _item_problems(item)]
    if len(final) > MAX_EVIDENCE_ITEMS:
        problems.append(f"{len(final)} items, over {MAX_EVIDENCE_ITEMS}")
    if [i.id for i in final] != [f"E{n}" for n in range(1, len(final) + 1)]:
        problems.append("E-IDs not sequential")
    covered = {i.section for i in final if i.source in ("dailymed_label", "absence")}
    problems += [f"label section {s} has no item" for s in LABEL_SECTIONS if s not in covered]
    for ingredient in identity.ingredients:
        sections = {i.section for i in final if i.ingredient == ingredient}
        if not sections & {"faers_reaction", "faers_total", "faers"}:
            problems.append(f"{ingredient}: no FAERS item")
        if "recalls" not in sections:
            problems.append(f"{ingredient}: no recall item")

    print(f"label: {label.label_title} ({label.set_id}, tier {label.tie_breaker})")
    print(f"built {len(items)} items -> kept {len(final)}")
    for item in final:
        print(f"  {item.id:>3} {item.source:<14} {item.section:<26} {item.ingredient or '':<16} {item.text[:70]!r}")
    print(json.dumps(final[0].model_dump(), indent=2))
    for problem in problems:
        print(f"  PROBLEM: {problem}")
    return not problems


class _SmokeAnswer(BaseModel):
    word: str


_SMOKE_PROMPT = 'Reply with a JSON object whose "word" field is the lowercase word "ok".'


async def check_provider_call() -> bool:
    """CP3: one real complete_json call; prints which provider answered."""
    result, provider = await complete_json(_SMOKE_PROMPT, _SmokeAnswer, 50)
    print(json.dumps({"provider": provider, "result": result.model_dump()}))
    return result.word.strip().lower() == "ok"


class _InvalidKeys:
    """Replace the named API keys for the duration of a check; restore after."""

    def __init__(self, *names: str):
        self.names = names
        self.saved: dict[str, str | None] = {}

    def __enter__(self):
        self.saved = {name: os.environ.get(name) for name in self.names}
        for name in self.names:
            os.environ[name] = "invalid-key-for-smoke"

    def __exit__(self, *exc_info):
        for name, value in self.saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


async def check_groq_fallback_with_invalid_gemini_key() -> bool:
    """CP3: Gemini key invalid -> Groq answers (exercises the Groq call parameters)."""
    with _InvalidKeys("GOOGLE_API_KEY"):
        result, provider = await complete_json(_SMOKE_PROMPT, _SmokeAnswer, 50)
    print(json.dumps({"provider": provider, "result": result.model_dump()}))
    return provider == "groq" and result.word.strip().lower() == "ok"


async def check_providers_unavailable_with_invalid_keys() -> bool:
    """CP3: invalid keys on both providers -> ProvidersUnavailableError (never a result)."""
    with _InvalidKeys("GOOGLE_API_KEY", "GROQ_API_KEY"):
        try:
            result, provider = await complete_json(_SMOKE_PROMPT, _SmokeAnswer, 50)
        except ProvidersUnavailableError as exc:
            print(f"ProvidersUnavailableError: {exc}")
            return True
    print(json.dumps({"unexpected": provider, "result": result.model_dump()}))
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
    *[
        (f"cp2 evidence: '{name}' Full intent, all fields present, cap and order hold",
         lambda name=name: check_evidence_full(name))
        for name in ("warfarin", "metformin", "Ozempic", "tramadol", "Tylenol PM")
    ],
    ("cp3 providers: real complete_json call returns validated JSON",
     check_provider_call),
    ("cp3 providers: invalid Gemini key -> Groq fallback answers",
     check_groq_fallback_with_invalid_gemini_key),
    ("cp3 providers: invalid keys on both providers -> ProvidersUnavailableError",
     check_providers_unavailable_with_invalid_keys),
]


async def main() -> int:
    load_dotenv()  # LLM keys and models, read by providers at call time
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
