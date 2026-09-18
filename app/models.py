from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceStatus = Literal["confirmado", "estimado", "por_confirmar"]
AvailabilityStatus = Literal[
    "disponible",
    "sin_stock",
    "por_confirmar",
]
FulfillmentStatus = Literal[
    "suficiente",
    "insuficiente",
    "por_confirmar",
]
PriceReviewStatus = Literal[
    "not_required",
    "requires_review",
    "validated",
]
ConfidenceLevel = Literal["alta", "media", "baja"]


class Source(BaseModel):
    title: str
    url: str


class SupplierResearch(BaseModel):
    supplier_name: str
    supplier_type: str = "Por confirmar"
    city: str = "Por confirmar"
    region: str = "Por confirmar"
    country: str = "Colombia"

    product_match: str
    product_match_status: EvidenceStatus = "por_confirmar"
    product_match_sources: list[Source] = Field(default_factory=list)

    availability_text: str = "Por confirmar"
    availability_status: AvailabilityStatus = "por_confirmar"
    fulfillment_status: FulfillmentStatus = "por_confirmar"
    availability_sources: list[Source] = Field(default_factory=list)

    price_text: str = "Por confirmar"
    price_amount_cop: float | None = None
    price_basis: str = "Por confirmar"
    price_basis_quantity: float | None = None
    price_base_unit: str = "Por confirmar"
    price_cop_per_unit: float | None = None
    estimated_total_delivered_cop: float | None = None
    price_status: EvidenceStatus = "por_confirmar"
    price_sources: list[Source] = Field(default_factory=list)
    price_review_status: PriceReviewStatus = "not_required"
    price_review_reason: str | None = None
    price_review_validated_at: str | None = None

    credit_terms: str = "Por confirmar"
    credit_days: int | None = None
    credit_status: EvidenceStatus = "por_confirmar"
    credit_sources: list[Source] = Field(default_factory=list)

    delivery_time: str = "Por confirmar"
    delivery_days: float | None = None
    delivery_status: EvidenceStatus = "por_confirmar"
    delivery_sources: list[Source] = Field(default_factory=list)

    certifications: list[str] = Field(default_factory=list)
    certifications_status: EvidenceStatus = "por_confirmar"
    certifications_sources: list[Source] = Field(default_factory=list)

    capacity: str = "Por confirmar"
    capacity_status: EvidenceStatus = "por_confirmar"
    capacity_sources: list[Source] = Field(default_factory=list)

    phone: str = "Por confirmar"
    email: str = "Por confirmar"
    website: str = "Por confirmar"
    contact_sources: list[Source] = Field(default_factory=list)

    evidence_summary: str
    confidence: ConfidenceLevel = "media"
    sources: list[Source] = Field(default_factory=list)


class PurchaseRequestInterpretation(BaseModel):
    interpreted_request: str
    product: str
    quantity: str | None = None
    destination: str | None = None
    required_specifications: list[str] = Field(default_factory=list)
    is_purchase_request: bool = True


class ResearchResult(BaseModel):
    interpreted_request: str
    product: str
    quantity: str
    destination: str
    required_specifications: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    suppliers: list[SupplierResearch] = Field(default_factory=list)
    recommendation_summary: str
    pending_questions: list[str] = Field(default_factory=list)


class RankedSupplier(BaseModel):
    rank: int
    score: float
    price_score: float
    credit_score: float
    delivery_score: float
    certifications_score: float
    evidence_score: float
    supplier: SupplierResearch


class ResearchResponse(BaseModel):
    research_id: int
    result: ResearchResult
    ranking: list[RankedSupplier]
    source_count: int
