import uuid
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PipelineContext:
    # Step 1 inputs
    raw_input_id: uuid.UUID
    source_id: str
    source_type: str
    name_raw: str
    barcode: str | None

    # Step 2: barcode
    barcode_type: str | None = None

    # Step 3: normalize
    name_normalized: str | None = None
    language: str | None = None          # "ru" / "uz" / "unknown"
    tokens: list[str] = field(default_factory=list)

    # Step 4: extract
    brand_id: int | None = None
    brand_name: str | None = None        # UPPERCASE
    product_type_id: int | None = None
    product_type_name: str | None = None
    variant: str | None = None
    quantity_value: Decimal | None = None
    quantity_unit: str | None = None
    package_code: str | None = None

    # Step 5: match
    product_id: uuid.UUID | None = None
    is_new: bool = False

    # Step 6: mxik
    mxik_code: str | None = None
    mxik_package_code: int | None = None
    mxik_is_group_code: bool = False
    mxik_confidence: Decimal | None = None

    # Step 7: generate
    name_canonical: str | None = None
    name_pos: str | None = None          # <=20
    name_receipt: str | None = None      # <=40
    name_catalog: str | None = None

    # Step 8: quality
    confidence_score: float = 0.0
    completeness_score: float = 0.0
    issues: list[str] = field(default_factory=list)
    review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    field_sources: dict = field(default_factory=dict)

    # passthrough from intake payload
    extra: dict = field(default_factory=dict)
