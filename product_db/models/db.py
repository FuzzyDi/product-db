import enum
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey, Integer,
    Numeric, SmallInteger, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ProductStatus(str, enum.Enum):
    candidate = "candidate"
    draft = "draft"
    verified = "verified"
    certified = "certified"


class BarcodeType(str, enum.Enum):
    ean13 = "ean13"
    ean8 = "ean8"
    upc_a = "upc_a"
    gs1_128 = "gs1_128"
    internal_weight = "internal_weight"
    internal_price = "internal_price"
    internal_unit = "internal_unit"


class DecisionType(str, enum.Enum):
    confirm_mxik = "confirm_mxik"
    confirm_package_code = "confirm_package_code"
    confirm_product = "confirm_product"
    correct_field = "correct_field"
    reject_match = "reject_match"
    merge_products = "merge_products"


# ---------------------------------------------------------------------------
# MXIK (fiscal layer)
# ---------------------------------------------------------------------------

class MxikCatalog(Base):
    __tablename__ = "mxik_catalog"

    id = Column(Integer, primary_key=True)
    mxik = Column(String(17), unique=True, nullable=False, index=True)
    mxik_name_ru = Column(Text)
    mxik_name_uz = Column(Text)
    mxik_name_lat = Column(Text)
    international_code = Column(String(20), index=True)
    label = Column(SmallInteger, nullable=False, default=0)
    label_for_check = Column(SmallInteger, nullable=False, default=0)
    cash_sale = Column(SmallInteger, nullable=False, default=1)
    is_group_code = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at_ms = Column(BigInteger)
    updated_at_ms = Column(BigInteger)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    search_vector = Column(TSVECTOR)

    packages = relationship("MxikPackage", back_populates="catalog", cascade="all, delete-orphan")


class MxikPackage(Base):
    __tablename__ = "mxik_packages"

    id = Column(Integer, primary_key=True)
    catalog_id = Column(Integer, ForeignKey("mxik_catalog.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(Integer, unique=True, nullable=False)
    package_type = Column(SmallInteger, nullable=False)  # 1=штучный 2=весовой 3=прочий
    name_ru = Column(Text)
    name_uz = Column(Text)
    name_lat = Column(Text)

    catalog = relationship("MxikCatalog", back_populates="packages")


class MxikSyncLog(Base):
    __tablename__ = "mxik_sync_log"

    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(20), nullable=False)  # running / success / failed
    records_total = Column(Integer)
    records_added = Column(Integer)
    records_updated = Column(Integer)
    records_deactivated = Column(Integer)
    error_message = Column(Text)


# ---------------------------------------------------------------------------
# Reference tables
# ---------------------------------------------------------------------------

class Manufacturer(Base):
    __tablename__ = "manufacturers"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    country = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    brands = relationship("Brand", back_populates="manufacturer")


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True)
    name_canonical = Column(String(255), unique=True, nullable=False)  # always UPPERCASE
    manufacturer_id = Column(Integer, ForeignKey("manufacturers.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    manufacturer = relationship("Manufacturer", back_populates="brands")
    aliases = relationship("BrandAlias", back_populates="brand", cascade="all, delete-orphan")


class BrandAlias(Base):
    __tablename__ = "brand_aliases"

    id = Column(Integer, primary_key=True)
    brand_id = Column(Integer, ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(255), nullable=False, index=True)
    source = Column(String(50))  # operator / auto
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    brand = relationship("Brand", back_populates="aliases")


class ProductType(Base):
    __tablename__ = "product_types"

    id = Column(Integer, primary_key=True)
    name_ru = Column(String(255), nullable=False)
    name_uz_latn = Column(String(255))
    name_uz_cyrl = Column(String(255))
    keywords_ru = Column(ARRAY(Text))
    keywords_uz = Column(ARRAY(Text))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("Category", remote_side=[id])


class UOM(Base):
    __tablename__ = "uom"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)  # ml, l, g, kg, pcs
    name_ru = Column(String(100))
    name_uz_latn = Column(String(100))
    name_uz_cyrl = Column(String(100))
    base_unit = Column(String(20))  # ml→l, g→kg
    factor = Column(Numeric(18, 6))  # 1ml = 0.001 l


class PackageType(Base):
    __tablename__ = "package_types"

    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False)  # PET, GLASS, TETRA, BOX…
    name_ru = Column(String(255))


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

class Product(Base):
    __tablename__ = "products"

    product_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(String(20), nullable=False, default=ProductStatus.candidate)

    # Names
    name_raw = Column(Text)
    name_normalized = Column(Text)
    name_canonical = Column(Text)
    name_pos = Column(String(20))       # кассовый чек <=20
    name_receipt = Column(String(40))   # расширенный чек <=40
    name_uz_latn = Column(Text)
    name_catalog = Column(Text)
    name_erp = Column(Text)

    # Brand / manufacturer
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    brand_name = Column(String(255))    # денормализованный UPPERCASE
    manufacturer_id = Column(Integer, ForeignKey("manufacturers.id"), nullable=True)
    subbrand = Column(String(255))

    # Classification
    product_type_id = Column(Integer, ForeignKey("product_types.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    variant = Column(String(255))

    # Quantity
    quantity_value = Column(Numeric(12, 4))
    quantity_unit = Column(String(20))
    base_quantity = Column(Numeric(12, 4))
    base_unit = Column(String(20))
    sale_unit = Column(String(20))

    # Package
    package_code = Column(String(50))

    # MXIK (dangerous fields — manual only)
    mxik_code = Column(String(17), index=True)
    mxik_package_code = Column(Integer)
    mxik_is_group_code = Column(Boolean, default=False)
    mxik_confidence = Column(Numeric(4, 3))

    # Fiscal flags (dangerous — from MXIK, manual only)
    label_required = Column(SmallInteger)
    label_for_check = Column(SmallInteger)
    cash_sale = Column(SmallInteger)

    # Quality
    quality_status = Column(String(20))
    confidence_score = Column(Numeric(4, 3))
    completeness_score = Column(Numeric(4, 3))
    issues = Column(ARRAY(Text))
    review_required = Column(Boolean, nullable=False, default=False)
    review_reasons = Column(ARRAY(Text))
    field_sources = Column(JSONB)       # {"brand_id": "source_id:xxx", ...}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    barcodes = relationship("ProductBarcode", back_populates="product", cascade="all, delete-orphan")
    external_codes = relationship("ExternalCode", back_populates="product", cascade="all, delete-orphan")


class ProductBarcode(Base):
    __tablename__ = "product_barcodes"

    id = Column(Integer, primary_key=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False, index=True)
    barcode = Column(String(50), nullable=False, index=True)
    barcode_type = Column(String(20), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="barcodes")


# ---------------------------------------------------------------------------
# Input data
# ---------------------------------------------------------------------------

class RawInputLog(Base):
    __tablename__ = "raw_input_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String(100), nullable=False, index=True)   # откуда пришло
    source_type = Column(String(50))                               # api / file / batch
    payload = Column(JSONB, nullable=False)                        # иммутабельно
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=True)
    status = Column(String(20), nullable=False, default="pending") # pending / processed / failed
    error = Column(Text)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))


class ExternalCode(Base):
    __tablename__ = "external_codes"

    id = Column(Integer, primary_key=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(100), nullable=False)
    code = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="external_codes")


# ---------------------------------------------------------------------------
# Quality management
# ---------------------------------------------------------------------------

class OperatorDecision(Base):
    __tablename__ = "operator_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False, index=True)
    operator_id = Column(String(100), nullable=False)
    decision_type = Column(String(30), nullable=False)
    field_name = Column(String(100))
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(Integer, primary_key=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.product_id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    existing_value = Column(JSONB)
    incoming_value = Column(JSONB)
    source_id = Column(String(100))
    resolved = Column(Boolean, nullable=False, default=False)
    resolved_by = Column(String(100))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class QualityStat(Base):
    __tablename__ = "quality_stats"

    id = Column(Integer, primary_key=True)
    period_date = Column(DateTime(timezone=True), nullable=False)
    total_products = Column(Integer)
    with_brand = Column(Integer)
    with_mxik = Column(Integer)
    with_barcode = Column(Integer)
    auto_confirmed = Column(Integer)
    review_queue_size = Column(Integer)
    avg_confidence = Column(Numeric(4, 3))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

class ProductTypeMxikMap(Base):
    __tablename__ = "product_type_mxik_map"

    id = Column(Integer, primary_key=True)
    product_type_id = Column(Integer, ForeignKey("product_types.id"), nullable=False)
    mxik_group_code = Column(String(17), nullable=False)  # заканчивается на 000000
    confidence = Column(Numeric(4, 3), nullable=False, default=0.5)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
