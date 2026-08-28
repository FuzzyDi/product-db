"""Pydantic схемы для API."""
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------

class ProductIntakeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    barcode: str | None = None
    source_id: str = Field(..., min_length=1, max_length=100)
    extra: dict[str, Any] = Field(default_factory=dict)


class BatchIntakeRequest(BaseModel):
    items: list[ProductIntakeRequest] = Field(..., min_length=1, max_length=1000)
    source_type: str = "batch"


class IntakeResponse(BaseModel):
    raw_input_id: uuid.UUID
    product_id: uuid.UUID
    is_new: bool
    confidence_score: float
    review_required: bool
    issues: list[str]
    status: str


class IntakeStatusResponse(BaseModel):
    raw_input_id: uuid.UUID
    product_id: uuid.UUID | None
    status: str
    error: str | None


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

class ProductResponse(BaseModel):
    product_id: uuid.UUID
    status: str
    name_raw: str | None
    name_normalized: str | None = None
    name_canonical: str | None
    name_uz_latn: str | None = None
    name_pos: str | None
    name_receipt: str | None
    brand_name: str | None
    brand_id: int | None = None
    subbrand: str | None = None
    product_type_id: int | None
    category_id: int | None = None
    quantity_value: Decimal | None
    quantity_unit: str | None
    package_code: str | None
    mxik_code: str | None
    mxik_package_code: int | None
    mxik_is_group_code: bool | None
    mxik_confidence: Decimal | None
    label_required: int | None
    label_for_check: int | None
    cash_sale: int | None
    confidence_score: Decimal | None
    completeness_score: Decimal | None
    issues: list[str] | None
    review_required: bool
    review_reasons: list[str] | None
    barcodes: list[str] = []

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    offset: int
    limit: int


class ProductUpdateRequest(BaseModel):
    """Обновление только безопасных полей."""
    name_canonical: str | None = Field(None, max_length=500)
    name_uz_latn: str | None = Field(None, max_length=500)
    name_pos: str | None = Field(None, max_length=20)
    name_receipt: str | None = Field(None, max_length=40)
    brand_name: str | None = Field(None, max_length=255)
    product_type_id: int | None = None
    variant: str | None = None
    subbrand: str | None = None
    package_code: str | None = None
    category_id: int | None = None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class PipelineStatsResponse(BaseModel):
    total_products: int
    by_status: dict[str, int]
    review_queue_size: int
    review_group_mxik_size: int = 0
    review_non_group_size: int = 0
    review_breakdown: dict[str, int] = {}
    with_brand: int
    with_mxik: int
    with_barcode: int
    with_category: int = 0
    with_type: int = 0
    certified_today: int = 0


class MxikHealthResponse(BaseModel):
    last_sync_status: str | None
    last_sync_at: str | None
    total_records: int
    active_records: int


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    meta: dict = Field(default_factory=dict)
    error: str | None = None
