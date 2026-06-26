from pydantic import Field

from backend.models.base import BaseSchema
from backend.models.enums import ProfileType


class MedicationReport(BaseSchema):
    profile_used: ProfileType
    drug_name: str
    summary: str
    key_findings: list[str]
    warnings: list[str]
    contraindications: list[str]
    recalls: list[str]
    adverse_events: list[str]
    interactions: list[str]
    limitations: list[str]
    sources_used: list[str]
    completeness_score: float = Field(ge=0.0, le=1.0)
