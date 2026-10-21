from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.models.base import BaseSchema
from backend.models.enums import InteractionSeverity, ProfileType, RecallClassification


class RecallRecord(BaseSchema):
    recall_number: str
    reason: str
    classification: RecallClassification
    recall_date: datetime | None
    status: str
    product_description: str


class AdverseEvent(BaseSchema):
    term: str
    count: int
    serious: bool


class DrugInteraction(BaseSchema):
    drug_name: str
    severity: InteractionSeverity
    description: str


class DrugIdentity(BaseSchema):
    input_name: str
    normalized_name: str
    generic_name: str | None
    rxcui: str | None
    ingredients: list[str]
    brand_names: list[str]


class LabelEvidence(BaseSchema):
    label_title: str
    set_id: str
    effective_date: str | None  # YYYY-MM-DD from OpenFDA effective_time
    url: str
    tie_breaker: int = Field(ge=1, le=4)  # PROJECT.md Section 5.4 rule that picked the label
    skipped_set_ids: list[str]  # SPLs skipped because OpenFDA had no label
    boxed_warnings: list[str]
    indications_and_usage: list[str]
    dosage_and_administration: list[str]
    contraindications: list[str]
    precautions: list[str]
    drug_interactions: list[str]


class RecallEvidence(BaseSchema):
    recalls: list[RecallRecord]
    total_count: int
    query_url: str  # openFDA enforcement query, cited by recall evidence items


class AdverseEventEvidence(BaseSchema):
    events: list[AdverseEvent]
    total_count: int
    query_url: str  # openFDA FAERS count query, cited by FAERS evidence items


class InteractionEvidence(BaseSchema):
    interactions: list[DrugInteraction]
    total_count: int


class EvidenceMetadata(BaseSchema):
    sources_attempted: int
    sources_succeeded: int
    sources_failed: int
    successful_sources: list[str]
    failed_sources: list[str]
    completeness_score: float = Field(ge=0.0, le=1.0)
    retrieved_at: datetime


class MedicationEvidence(BaseSchema):
    profile_used: ProfileType
    drug_identity: DrugIdentity
    label_evidence: LabelEvidence | None
    recall_evidence: RecallEvidence | None
    adverse_event_evidence: AdverseEventEvidence | None
    interaction_evidence: InteractionEvidence | None
    metadata: EvidenceMetadata


EvidenceSource = Literal["dailymed_label", "openfda_recall", "faers", "absence"]


class EvidenceItem(BaseSchema):
    """One passage the LLM may cite (PROJECT.md Section 6)."""

    id: str  # "E1".. per request, shown to LLM; "" until the store assigns it
    internal_id: str  # sha1(source|set_id|section|chunk_index|text)[:12]
    product: str
    ingredient: str | None  # FAERS and recall items
    rxcui: str
    source: EvidenceSource
    section: str
    text: str = Field(max_length=600)
    url: str
    label_title: str | None
    label_set_id: str | None
    label_effective_date: str | None
    retrieved_at: str  # ISO 8601 UTC
