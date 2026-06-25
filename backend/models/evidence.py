from datetime import datetime

from pydantic import Field

from backend.models.base import BaseSchema
from backend.models.enums import InteractionSeverity, ProfileType, RecallClassification


class RecallRecord(BaseSchema):
    recall_number: str
    reason: str
    classification: RecallClassification
    recall_date: datetime | None
    status: str


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
    brand_names: list[str]


class LabelEvidence(BaseSchema):
    boxed_warnings: list[str]
    contraindications: list[str]
    precautions: list[str]
    drug_interactions: list[str]


class RecallEvidence(BaseSchema):
    recalls: list[RecallRecord]
    total_count: int


class AdverseEventEvidence(BaseSchema):
    events: list[AdverseEvent]
    total_count: int


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
