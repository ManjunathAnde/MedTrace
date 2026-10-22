"""
Prescription Check, deterministic parts (PROJECT.md Section 9).

  9.1 input parsing     parse_drug_list, input_outcome
  9.2 resolution        resolve_products (RxNorm exact; misses listed, not fatal)
  9.3 evidence          gather_product_evidence (4 interaction-relevant sections),
                        number_evidence (E-IDs unique across the request)
  9.4 candidate search  match_names, find_pair_candidates (pure; no hit -> no LLM)
  9.6 after verifying   pair_card, sort_by_severity, combined_provider (pure)
  9.7 severity          severity_for (pure; highest wins, rule recorded)
  9.8 recalls           gather_recall_evidence (per unique ingredient)

The endpoint (backend/main.py) runs the interaction agent and the verifier
between these steps.
DailyMed and recalls degrade (a failure becomes a gap); an RxNorm outage
propagates as RxNormServiceError so the endpoint fails loud.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from typing import Literal

from backend.apis.dailymed import DailyMedError, DailyMedNotFoundError, fetch_label_evidence
from backend.apis.fda_recall import FDARecallServiceError, fetch_recall_evidence
from backend.apis.rxnorm import RxNormDrugNotFoundError, fetch_drug_identity
from backend.core.router import NOT_RECOGNIZED_MESSAGE
from backend.evidence.store import RECALLS, build_label_items, build_recall_items
from backend.llm.medication_extractor import is_plausible_name
from backend.models.evidence import DrugIdentity, EvidenceItem, LabelEvidence

logger = logging.getLogger(__name__)

MAX_PRESCRIPTION_DRUGS = 5
MIN_RESOLVED_DRUGS = 2
MIN_MATCH_NAME_CHARS = 4

TOO_FEW_MESSAGE = "Add at least two recognized medications to run a check."
TOO_MANY_MESSAGE = f"Prescription Check takes at most {MAX_PRESCRIPTION_DRUGS} medications."
NO_DOCUMENTED_INTERACTION = "No interaction documented in either FDA label."
FOOTER = "Class-level interactions were not checked."

# Section 9.3, searched for each other's names; Section 6 order.
PRESCRIPTION_SECTIONS = ["drug_interactions", "contraindications", "boxed_warning", "warnings"]

Severity = Literal["High", "Moderate", "Info"]


# --- 9.1 input ---

def parse_drug_list(drugs: list[str]) -> list[str]:
    """Trim, drop empty, dedupe case-insensitive (first spelling kept)."""
    seen: dict[str, str] = {}
    for name in (d.strip() for d in drugs):
        if name and name.lower() not in seen:
            seen[name.lower()] = name
    return list(seen.values())


def input_outcome(names: list[str]) -> Literal["TOO_MANY", "TOO_FEW"] | None:
    """Count rule before any API call; None means continue to resolution."""
    if len(names) > MAX_PRESCRIPTION_DRUGS:
        return "TOO_MANY"
    if len(names) < MIN_RESOLVED_DRUGS:
        return "TOO_FEW"
    return None


# --- 9.2 resolution ---

@dataclass
class Resolution:
    input_name: str
    identity: DrugIdentity | None = None
    message: str | None = None  # set when not recognized

    @property
    def resolved(self) -> bool:
        return self.identity is not None


async def resolve_products(names: list[str]) -> list[Resolution]:
    """
    RxNorm exact per entry, in input order. A failed sanity check or an RxNorm
    miss is a NOT_RECOGNIZED entry; RxNormServiceError propagates.
    """
    resolutions = []
    for name in names:
        if not is_plausible_name(name):
            logger.info("prescription check: %r fails the sanity check", name)
            resolutions.append(Resolution(name, message=NOT_RECOGNIZED_MESSAGE.format(name=name)))
            continue
        try:
            identity = await fetch_drug_identity(name)
        except RxNormDrugNotFoundError:
            resolutions.append(Resolution(name, message=NOT_RECOGNIZED_MESSAGE.format(name=name)))
            continue
        resolutions.append(Resolution(name, identity=identity))
    return resolutions


# --- 9.3 evidence per product ---

@dataclass
class ProductEvidence:
    identity: DrugIdentity
    label: LabelEvidence | None
    items: list[EvidenceItem] = field(default_factory=list)  # label chunks and absence items

    @property
    def product(self) -> str:
        return self.identity.normalized_name

    @property
    def passages(self) -> list[EvidenceItem]:
        """Label text that candidate search reads (absence items excluded)."""
        return [i for i in self.items if i.source == "dailymed_label"]


def number_evidence(
    products: list["ProductEvidence"], recall_items: list[EvidenceItem]
) -> list[EvidenceItem]:
    """
    E1..En unique across the request: each product's label items in input
    order, then recall items. Product items are renumbered in place; the
    numbered recall items are returned.
    """
    n = 0

    def numbered(items: list[EvidenceItem]) -> list[EvidenceItem]:
        nonlocal n
        out = []
        for item in items:
            n += 1
            out.append(item.model_copy(update={"id": f"E{n}"}))
        return out

    for p in products:
        p.items = numbered(p.items)
    return numbered(recall_items)


async def gather_product_evidence(
    identities: list[DrugIdentity], retrieved_at: str | None = None
) -> tuple[list[ProductEvidence], list[str]]:
    """
    Label selection per product and the four Section 9.3 sections, all chunks
    (no 20-item cap: code searches every passage, and the agent sees only one
    pair's candidates). E-IDs are assigned afterwards by number_evidence.
    """
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    products, gaps = [], []
    for identity in identities:
        product = identity.normalized_name
        label, items = None, []
        if identity.rxcui:
            try:
                label = await fetch_label_evidence(
                    identity.rxcui, identity.input_name, len(identity.ingredients) == 1
                )
                items = build_label_items(product, identity.rxcui, label, PRESCRIPTION_SECTIONS, retrieved_at)
            except DailyMedNotFoundError:
                gaps.append(f"No FDA label was found for {product}.")
            except DailyMedError as exc:
                logger.warning("label retrieval failed for %s: %s", product, exc)
                gaps.append(f"The FDA label for {product} could not be retrieved.")
        products.append(ProductEvidence(identity=identity, label=label, items=items))
    return products, gaps


# --- 9.4 candidate search (pure) ---

def match_names(identity: DrugIdentity) -> list[str]:
    """A product's search names: ingredients + brand names, lowercased, under 4 chars dropped."""
    names = dict.fromkeys(n.strip().lower() for n in identity.ingredients + identity.brand_names)
    return [n for n in names if len(n) >= MIN_MATCH_NAME_CHARS]


@dataclass
class Candidate:
    item: EvidenceItem   # the passage that names the other product
    matched_name: str    # which of the other product's names it contains


def _search(passages: list[EvidenceItem], names: list[str]) -> list[Candidate]:
    patterns = [(n, re.compile(rf"\b{re.escape(n)}\b", re.IGNORECASE)) for n in names]
    found = []
    for item in passages:
        for name, pattern in patterns:
            if pattern.search(item.text):
                found.append(Candidate(item, name))
                break  # one candidate per passage
    return found


def find_pair_candidates(
    passages_a: list[EvidenceItem], names_a: list[str],
    passages_b: list[EvidenceItem], names_b: list[str],
) -> list[Candidate]:
    """Section 9.4: A's passages naming B, then B's passages naming A. Empty: no LLM call."""
    return _search(passages_a, names_b) + _search(passages_b, names_a)


@dataclass
class PairCandidates:
    pair: tuple[str, str]
    a: ProductEvidence
    b: ProductEvidence
    candidates: list[Candidate]


def search_all_pairs(products: list[ProductEvidence]) -> list[PairCandidates]:
    """Every unordered product pair, in input order, with its candidates."""
    results = []
    for a, b in combinations(products, 2):
        candidates = find_pair_candidates(
            a.passages, match_names(a.identity), b.passages, match_names(b.identity)
        )
        logger.info("pair %s + %s: %d candidates %s", a.product, b.product, len(candidates),
                    [(c.item.product, c.item.section, c.matched_name) for c in candidates])
        results.append(PairCandidates((a.product, b.product), a, b, candidates))
    return results


# --- 9.7 severity (pure) ---

_HIGH_SECTIONS = ("boxed_warning", "contraindications")
_HIGH_PHRASES = ("contraindicated", "avoid", "do not use", "not recommended", "should not be used")
_MODERATE_PHRASES = (
    "monitor", "adjust", "reduce the dose", "dose reduction", "increased risk",
    "may increase", "may decrease",
)
_RANK: dict[Severity, int] = {"High": 2, "Moderate": 1, "Info": 0}


def _item_severity(item: EvidenceItem) -> tuple[Severity, str]:
    text = item.text.lower()
    if item.section in _HIGH_SECTIONS:
        return "High", f"section {item.section}"
    for phrase in _HIGH_PHRASES:
        if phrase in text:
            return "High", f"text has '{phrase}'"
    for phrase in _MODERATE_PHRASES:
        if phrase in text:
            return "Moderate", f"text has '{phrase}'"
    return "Info", "no severity signal"


def severity_for(cited: list[EvidenceItem]) -> tuple[Severity, str]:
    """
    Section 9.7, over the passages cited by kept claims: highest wins; on a tie
    the first cited passage's rule is shown. The rule names its passage's id.
    """
    best: tuple[Severity, str] = ("Info", "no severity signal")
    for item in cited:
        severity, rule = _item_severity(item)
        if _RANK[severity] > _RANK[best[0]]:
            best = (severity, f"{rule} ({item.id})")
    return best


# --- 9.6 after verification (pure) ---

NO_INTERACTION_STATED_RULE = "Label states no clinically significant interaction"
NEEDS_REVIEW_UNVERIFIED = "Mentioned in a label; could not be verified automatically."


def pair_card(finding: str | None, cited: list[EvidenceItem]) -> tuple[Severity, str] | None:
    """
    Section 9.6: (severity, rule) when the pair is shown as a card, None when it
    goes to needs_review. `cited` = passages cited by the kept claims.
      INTERACTION_DOCUMENTED, 1+ kept -> card, Section 9.7 severity
      NO_INTERACTION_STATED,  1+ kept -> Info card
      0 kept, UNCLEAR, or no finding  -> needs_review (NO_INTERACTION_STATED
                                         with 0 kept too: owner, 2026-10-21)
    """
    if not cited:
        return None
    if finding == "INTERACTION_DOCUMENTED":
        return severity_for(cited)
    if finding == "NO_INTERACTION_STATED":
        return "Info", NO_INTERACTION_STATED_RULE
    return None


def sort_by_severity(cards: list) -> list:
    """Cards High, Moderate, Info; input order kept within a level."""
    return sorted(cards, key=lambda card: -_RANK[card.severity])


def combined_provider(providers: list[str | None]) -> str | None:
    """meta.verifier_provider over several calls: "groq" if any fell back, else "gemini", else None."""
    if "groq" in providers:
        return "groq"
    return "gemini" if "gemini" in providers else None


# --- 9.8 recalls ---

async def gather_recall_evidence(
    products: list[ProductEvidence], retrieved_at: str | None = None
) -> tuple[list[EvidenceItem], list[str]]:
    """Newest recall records per unique ingredient (first product naming it), or an absence item."""
    retrieved_at = retrieved_at or datetime.now(timezone.utc).isoformat()
    items, gaps, seen = [], [], set()
    for p in products:
        for ingredient in p.identity.ingredients:
            if ingredient.lower() in seen:
                continue
            seen.add(ingredient.lower())
            try:
                recalls = await fetch_recall_evidence(ingredient)
            except FDARecallServiceError as exc:
                logger.warning("recall retrieval failed for %s: %s", ingredient, exc)
                gaps.append(f"FDA enforcement (recall) records could not be retrieved for {ingredient}.")
                continue
            items += build_recall_items(p.product, p.identity.rxcui or "", ingredient, recalls,
                                        RECALLS, retrieved_at)
    return items, gaps
