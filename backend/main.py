from dotenv import load_dotenv
load_dotenv()

import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.apis.dailymed import DailyMedError, DailyMedNotFoundError, fetch_label_evidence
from backend.apis.fda_recall import FDARecallServiceError, fetch_recall_evidence
from backend.apis.openfda import OpenFDAServiceError, fetch_adverse_event_evidence
from backend.apis.rxnorm import RxNormDrugNotFoundError, RxNormServiceError, fetch_drug_identity
from backend.cache.report_cache import (
    build_cache_key,
    build_prescription_cache_key,
    close_report_cache,
    get_cached_prescription_check,
    get_cached_response,
    store_cached_prescription_check,
    store_cached_response,
)
from backend.core.prescription_check import (
    FOOTER,
    MIN_RESOLVED_DRUGS,
    NEEDS_REVIEW_UNVERIFIED,
    TOO_FEW_MESSAGE,
    TOO_MANY_MESSAGE,
    Resolution,
    combined_provider,
    gather_product_evidence,
    gather_recall_evidence,
    input_outcome,
    number_evidence,
    pair_card,
    parse_drug_list,
    resolve_products,
    search_all_pairs,
    sort_by_severity,
)
from backend.core.router import (
    INTENT_NAMES,
    SOURCES_BY_PROFILE,
    blocked_outcome,
    drug_count_outcome,
    final_status,
    not_recognized_outcome,
    resolve_profile,
    unavailable_outcome,
)
from backend.evidence.store import (
    assemble_evidence,
    build_faers_items,
    build_label_items,
    build_recall_items,
)
from backend.llm.intent_classifier import classify_query_intent
from backend.llm.interaction_agent import NOT_EVALUATED_REASON, PairInput, evaluate_pair
from backend.llm.medication_extractor import extract_medication_names
from backend.llm.providers import ProvidersUnavailableError
from backend.llm.safety_classifier import classify_safety_category
from backend.llm.synthesizer import SynthInput, synthesize_claims
from backend.models.claims import VerifiedClaimSet
from backend.models.enums import PrescriptionCheckStatus, ProfileType, SafetyCategory, Wall1Action
from backend.models.evidence import DrugIdentity, EvidenceItem, LabelEvidence
from backend.models.report import (
    EarlyOutcome,
    InteractionCard,
    InvestigateResponse,
    LabelRef,
    NeedsReview,
    PrescriptionCheckMeta,
    PrescriptionCheckResponse,
    RecallRef,
    RemovedClaim,
    ResolutionOut,
    ResolvedDrugOut,
    ResponseClaim,
    ResponseMeta,
)
from backend.safety.filter import check_wall1
from backend.verifier.verifier import VERIFIER_UNAVAILABLE, verify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
# httpx logs every request URL at INFO; Upstash's URL comes from the environment.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Medication Intelligence Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvestigateRequest(BaseModel):
    query: str


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred"},
    )


def _meta(t0: float, llm_calls: int, synthesizer_provider=None, cache_hit: bool = False,
          verified: bool = False, verifier_provider=None) -> ResponseMeta:
    return ResponseMeta(
        latency_ms=int((time.perf_counter() - t0) * 1000),
        llm_calls=llm_calls,
        verifier_provider=verifier_provider,
        cache_hit=cache_hit,
        verified=verified,  # True once claims have been through the verifier
        synthesizer_provider=synthesizer_provider,
    )


def _early_response(outcome: EarlyOutcome, t0: float, llm_calls: int, intent: str | None = None,
                    drug: ResolvedDrugOut | None = None) -> InvestigateResponse:
    logger.info("investigate status=%s block_type=%s intent=%s", outcome.status.value,
                outcome.block_type.value if outcome.block_type else None, intent)
    return InvestigateResponse(
        status=outcome.status, message=outcome.message, block_type=outcome.block_type,
        redirect=outcome.redirect, intent=intent, drug=drug, meta=_meta(t0, llm_calls),
    )


def _drug_out(identity: DrugIdentity, label: LabelEvidence | None) -> ResolvedDrugOut:
    return ResolvedDrugOut(
        input_name=identity.input_name,
        rxcui=identity.rxcui,
        preferred_name=identity.normalized_name,
        ingredients=identity.ingredients,
        label=LabelRef(title=label.label_title, set_id=label.set_id,
                       effective_date=label.effective_date, url=label.url) if label else None,
    )


def _removed(verified: VerifiedClaimSet) -> list[RemovedClaim]:
    return [RemovedClaim(text=c.text, evidence_id=c.evidence_id, quote=c.quote,
                         verdict=c.verdict, reason=c.reason) for c in verified.cut]


async def _gather_evidence(
    identity: DrugIdentity, profile: ProfileType
) -> tuple[LabelEvidence | None, list[EvidenceItem], list[str]]:
    """
    Sources for the intent (Section 6), per ingredient for FAERS and recalls.
    DailyMed, FAERS and recalls degrade: a failure becomes a gap, never an error.
    """
    sources = SOURCES_BY_PROFILE[profile]
    product = identity.normalized_name
    retrieved_at = datetime.now(timezone.utc).isoformat()
    items: list[EvidenceItem] = []
    gaps: list[str] = []

    label = None
    if sources.label_sections and identity.rxcui:
        try:
            label = await fetch_label_evidence(
                identity.rxcui, identity.input_name, len(identity.ingredients) == 1
            )
            items += build_label_items(product, identity.rxcui, label, sources.label_sections, retrieved_at)
        except DailyMedNotFoundError:
            gaps.append(f"No FDA label was found for {product}.")
        except DailyMedError as exc:
            logger.warning("label retrieval failed for %s: %s", product, exc)
            gaps.append(f"The FDA label for {product} could not be retrieved.")

    for ingredient in identity.ingredients:
        if sources.faers_top_reactions is not None:
            try:
                faers = await fetch_adverse_event_evidence(ingredient)
                items += build_faers_items(product, identity.rxcui, ingredient, faers,
                                           sources.faers_top_reactions, retrieved_at)
            except OpenFDAServiceError as exc:
                logger.warning("FAERS retrieval failed for %s: %s", ingredient, exc)
                gaps.append(f"FAERS adverse event reports could not be retrieved for {ingredient}.")
        if sources.recalls is not None:
            try:
                recalls = await fetch_recall_evidence(ingredient)
                items += build_recall_items(product, identity.rxcui, ingredient, recalls,
                                            sources.recalls, retrieved_at)
            except FDARecallServiceError as exc:
                logger.warning("recall retrieval failed for %s: %s", ingredient, exc)
                gaps.append(f"FDA enforcement (recall) records could not be retrieved for {ingredient}.")

    return label, assemble_evidence(items), gaps


@app.post("/investigate", response_model=InvestigateResponse)
async def investigate(request: InvestigateRequest):
    """
    Ask MedTrace (PROJECT.md Section 4). Every expected outcome is HTTP 200 with a
    status; a genuine RxNorm outage is 503.
    """
    t0 = time.perf_counter()
    query = request.query.strip()
    llm_calls = 0

    # Wall 1 (rules): block or escalate, never clear
    wall1 = check_wall1(query)
    if wall1.action == Wall1Action.BLOCK:
        return _early_response(blocked_outcome(wall1.category), t0, llm_calls)

    # Wall 2 (LLM): not SAFE stops with zero data API calls; failure is UNAVAILABLE
    try:
        llm_calls += 1
        verdict, _ = await classify_safety_category(query)
    except ProvidersUnavailableError:
        return _early_response(unavailable_outcome(), t0, llm_calls)
    if verdict.safety != SafetyCategory.SAFE:
        return _early_response(blocked_outcome(verdict.safety), t0, llm_calls)

    # Verbatim extraction + code guard; failure is UNAVAILABLE, never the raw query
    try:
        llm_calls += 1
        drugs, _ = await extract_medication_names(query)
    except ProvidersUnavailableError:
        return _early_response(unavailable_outcome(), t0, llm_calls)

    llm_calls += 1
    intent_result, _ = await classify_query_intent(query)
    profile = resolve_profile(intent_result)
    intent = INTENT_NAMES[profile]

    count_outcome = drug_count_outcome(drugs, profile)
    if count_outcome is not None:
        return _early_response(count_outcome, t0, llm_calls, intent=intent)
    drug_name = drugs[0]

    cache_key = build_cache_key(drug_name, profile)
    cached = await get_cached_response(cache_key)
    if cached is not None:
        return cached.model_copy(update={"meta": cached.meta.model_copy(update={
            "cache_hit": True, "latency_ms": int((time.perf_counter() - t0) * 1000),
        })})

    # RxNorm exact: miss is NOT_RECOGNIZED (200); outage fails loud (503)
    try:
        identity = await fetch_drug_identity(drug_name)
    except RxNormDrugNotFoundError:
        return _early_response(not_recognized_outcome(drug_name), t0, llm_calls, intent=intent)
    except RxNormServiceError as exc:
        logger.error("RxNorm unavailable for %r: %s", drug_name, exc)
        return JSONResponse(
            status_code=503,
            content={"error": "rxnorm_unavailable", "message": "Drug name resolution is unavailable. Please try again."},
        )

    label, evidence, source_gaps = await _gather_evidence(identity, profile)

    if evidence:
        llm_calls += 1
    claim_set, synthesizer_provider = await synthesize_claims(SynthInput(
        question=query, intent=intent, product=identity.normalized_name, evidence=evidence,
    ))

    # Verifier (Section 8): only kept claims reach the user
    by_id = {item.id: item for item in evidence}
    verified = await verify(claim_set.claims, {item.id: item.text for item in evidence})
    if verified.verifier_provider is not None:
        llm_calls += 1
    kept = verified.kept
    gaps = source_gaps + claim_set.gaps
    status = final_status(verified.claims_kept, len(verified.cut), gaps)

    response = InvestigateResponse(
        status=status,
        intent=intent,
        drug=_drug_out(identity, label),
        claims=[ResponseClaim(text=c.text, section=by_id[c.evidence_id].section,
                              evidence_id=c.evidence_id, quote=c.quote) for c in kept],
        claims_total=verified.claims_total,
        claims_kept=verified.claims_kept,
        removed=_removed(verified),
        gaps=gaps,
        evidence={c.evidence_id: by_id[c.evidence_id] for c in kept},
        meta=_meta(t0, llm_calls, synthesizer_provider, verified=True,
                   verifier_provider=verified.verifier_provider),
    )
    logger.info(
        "investigate status=%s intent=%s drug=%r rxcui=%s evidence=%d claims=%d/%d gaps=%d "
        "llm_calls=%d latency_ms=%d",
        status.value, intent, drug_name, identity.rxcui, len(evidence), verified.claims_kept,
        verified.claims_total, len(gaps), llm_calls, response.meta.latency_ms,
    )
    await store_cached_response(cache_key, profile, response)
    return response


class PrescriptionCheckRequest(BaseModel):
    drugs: list[str]


def _resolution_out(resolution: Resolution, label: LabelEvidence | None) -> ResolutionOut:
    if not resolution.resolved:
        return ResolutionOut(input_name=resolution.input_name, status="NOT_RECOGNIZED",
                             message=resolution.message)
    drug = _drug_out(resolution.identity, label)
    return ResolutionOut(input_name=resolution.input_name, status="RESOLVED", rxcui=drug.rxcui,
                         preferred_name=drug.preferred_name, ingredients=drug.ingredients, label=drug.label)


@app.post("/prescription-check", response_model=PrescriptionCheckResponse)
async def prescription_check(request: PrescriptionCheckRequest):
    """
    Prescription Check (PROJECT.md Sections 4, 9). Every expected outcome is
    HTTP 200 with a status; a genuine RxNorm outage is 503.
    """
    t0 = time.perf_counter()
    llm_calls = 0

    def meta(pairs_checked=0, pairs_with_candidates=0, verifier_provider=None, verified=False):
        return PrescriptionCheckMeta(
            latency_ms=int((time.perf_counter() - t0) * 1000), llm_calls=llm_calls,
            pairs_checked=pairs_checked, pairs_with_candidates=pairs_with_candidates,
            verifier_provider=verifier_provider, cache_hit=False, verified=verified,
        )

    # 9.1 input: count rules before any API call
    names = parse_drug_list(request.drugs)
    early = input_outcome(names)
    if early is not None:
        status = PrescriptionCheckStatus(early)
        message = TOO_MANY_MESSAGE if early == "TOO_MANY" else TOO_FEW_MESSAGE
        logger.info("prescription check status=%s drugs=%d", status.value, len(names))
        return PrescriptionCheckResponse(status=status, message=message, meta=meta())

    # 9.2 resolution: misses listed, not fatal; RxNorm outage fails loud (503)
    try:
        resolutions = await resolve_products(names)
    except RxNormServiceError as exc:
        logger.error("RxNorm unavailable for prescription check %r: %s", names, exc)
        return JSONResponse(
            status_code=503,
            content={"error": "rxnorm_unavailable", "message": "Drug name resolution is unavailable. Please try again."},
        )
    identities = [r.identity for r in resolutions if r.resolved]
    if len(identities) < MIN_RESOLVED_DRUGS:
        logger.info("prescription check status=TOO_FEW resolved=%d", len(identities))
        return PrescriptionCheckResponse(
            status=PrescriptionCheckStatus.TOO_FEW, message=TOO_FEW_MESSAGE,
            resolution=[_resolution_out(r, None) for r in resolutions], meta=meta(),
        )

    # Cache only when every entry resolved, so the cached resolution list is the whole input
    all_resolved = len(identities) == len(resolutions)
    cache_key = build_prescription_cache_key([i.rxcui for i in identities]) if all_resolved else None
    if cache_key and (cached := await get_cached_prescription_check(cache_key)):
        typed = {r.identity.rxcui: r.input_name for r in resolutions}
        return cached.model_copy(update={
            "resolution": [e.model_copy(update={"input_name": typed.get(e.rxcui, e.input_name)})
                           for e in cached.resolution],
            "meta": cached.meta.model_copy(update={
                "cache_hit": True, "latency_ms": int((time.perf_counter() - t0) * 1000)}),
        })

    # 9.3 evidence, 9.8 recalls, E-IDs unique across the request; 9.4 candidates
    products, gaps = await gather_product_evidence(identities)
    recall_items, recall_gaps = await gather_recall_evidence(products)
    recall_items = number_evidence(products, recall_items)
    pairs = search_all_pairs(products)

    by_id = {item.id: item for p in products for item in p.items}
    by_id.update({item.id: item for item in recall_items})
    referenced: set[str] = {item.id for item in recall_items}
    cards, needs_review, no_documented = [], [], []
    verifier_providers: list[str | None] = []
    all_verified = True

    for pair in pairs:
        if not pair.candidates:
            no_documented.append(pair.pair)  # no LLM call
            continue
        candidate_ids = [c.item.id for c in pair.candidates]
        llm_calls += 1
        finding, _ = await evaluate_pair(PairInput(
            product_a=pair.a.product, ingredients_a=pair.a.identity.ingredients,
            product_b=pair.b.product, ingredients_b=pair.b.identity.ingredients,
            passages=[c.item for c in pair.candidates],
        ))
        if finding is None:
            all_verified = False
            referenced.update(candidate_ids)
            needs_review.append(NeedsReview(pair=pair.pair, evidence_ids=candidate_ids,
                                            reason=NOT_EVALUATED_REASON))
            continue

        # Verify against this pair's candidates only: citing any other passage is CUT_BAD_ID
        verified = await verify(finding.claims, {c.item.id: c.item.text for c in pair.candidates})
        if verified.verifier_provider is not None:
            llm_calls += 1
        verifier_providers.append(verified.verifier_provider)
        all_verified &= not any(c.reason == VERIFIER_UNAVAILABLE for c in verified.cut)
        removed = _removed(verified)
        referenced.update(c.evidence_id for c in verified.cut if c.evidence_id in by_id)

        cited = [by_id[c.evidence_id] for c in verified.kept]
        card = pair_card(finding.finding, cited)
        if card is None:
            referenced.update(candidate_ids)
            needs_review.append(NeedsReview(pair=pair.pair, evidence_ids=candidate_ids,
                                            reason=NEEDS_REVIEW_UNVERIFIED, removed=removed))
            continue
        severity, rule = card
        referenced.update(c.evidence_id for c in verified.kept)
        cards.append(InteractionCard(
            pair=pair.pair, finding=finding.finding, severity=severity, severity_rule=rule,
            claims=[ResponseClaim(text=c.text, section=by_id[c.evidence_id].section,
                                  evidence_id=c.evidence_id, quote=c.quote) for c in verified.kept],
            removed=removed,
        ))

    labels = {p.identity.rxcui: p.label for p in products}
    response = PrescriptionCheckResponse(
        status=PrescriptionCheckStatus.COMPLETE,
        resolution=[_resolution_out(r, labels.get(r.identity.rxcui) if r.resolved else None)
                    for r in resolutions],
        interactions=sort_by_severity(cards),
        needs_review=needs_review,
        no_documented_interaction=no_documented,
        recalls=[RecallRef(ingredient=item.ingredient, evidence_id=item.id) for item in recall_items],
        gaps=gaps + recall_gaps,
        evidence={i: by_id[i] for i in sorted(referenced, key=lambda i: int(i[1:]))},
        footer=FOOTER,
        meta=meta(len(pairs), sum(1 for p in pairs if p.candidates),
                  combined_provider(verifier_providers), verified=all_verified),
    )
    logger.info(
        "prescription check status=COMPLETE products=%d pairs=%d with_candidates=%d cards=%d "
        "needs_review=%d no_documented=%d llm_calls=%d verified=%s latency_ms=%d",
        len(products), len(pairs), response.meta.pairs_with_candidates, len(cards), len(needs_review),
        len(no_documented), llm_calls, all_verified, response.meta.latency_ms,
    )
    if cache_key:
        await store_cached_prescription_check(cache_key, response)
    return response


@app.on_event("shutdown")
async def shutdown_report_cache():
    await close_report_cache()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/profiles")
def list_profiles():
    return [p.value for p in ProfileType]
