"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "unaccent"')

    # ------------------------------------------------------------------
    # MXIK (fiscal layer)
    # ------------------------------------------------------------------
    op.create_table(
        "mxik_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mxik", sa.String(17), nullable=False),
        sa.Column("mxik_name_ru", sa.Text()),
        sa.Column("mxik_name_uz", sa.Text()),
        sa.Column("mxik_name_lat", sa.Text()),
        sa.Column("international_code", sa.String(20)),
        sa.Column("label", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("label_for_check", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("cash_sale", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("is_group_code", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at_ms", sa.BigInteger()),
        sa.Column("updated_at_ms", sa.BigInteger()),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("search_vector", postgresql.TSVECTOR()),
    )
    op.create_index("uq_mxik_catalog_mxik", "mxik_catalog", ["mxik"], unique=True)
    op.create_index("ix_mxik_catalog_international_code", "mxik_catalog", ["international_code"])
    op.create_index(
        "ix_mxik_catalog_search_vector",
        "mxik_catalog",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.create_table(
        "mxik_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_id", sa.Integer(), sa.ForeignKey("mxik_catalog.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.Integer(), nullable=False),
        sa.Column("package_type", sa.SmallInteger(), nullable=False),
        sa.Column("name_ru", sa.Text()),
        sa.Column("name_uz", sa.Text()),
        sa.Column("name_lat", sa.Text()),
    )
    op.create_index("uq_mxik_packages_code", "mxik_packages", ["code"], unique=True)
    op.create_index("ix_mxik_packages_catalog_id", "mxik_packages", ["catalog_id"])

    op.create_table(
        "mxik_sync_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("records_total", sa.Integer()),
        sa.Column("records_added", sa.Integer()),
        sa.Column("records_updated", sa.Integer()),
        sa.Column("records_deactivated", sa.Integer()),
        sa.Column("error_message", sa.Text()),
    )

    # ------------------------------------------------------------------
    # Reference tables
    # ------------------------------------------------------------------
    op.create_table(
        "manufacturers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_manufacturers_name", "manufacturers", ["name"], unique=True)

    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name_canonical", sa.String(255), nullable=False),
        sa.Column("manufacturer_id", sa.Integer(), sa.ForeignKey("manufacturers.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_brands_name_canonical", "brands", ["name_canonical"], unique=True)
    op.create_index(
        "ix_brands_name_canonical_trgm",
        "brands",
        ["name_canonical"],
        postgresql_using="gin",
        postgresql_ops={"name_canonical": "gin_trgm_ops"},
    )

    op.create_table(
        "brand_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_brand_aliases_brand_id", "brand_aliases", ["brand_id"])
    op.create_index("ix_brand_aliases_alias", "brand_aliases", ["alias"])
    op.create_index(
        "ix_brand_aliases_alias_trgm",
        "brand_aliases",
        ["alias"],
        postgresql_using="gin",
        postgresql_ops={"alias": "gin_trgm_ops"},
    )

    op.create_table(
        "product_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name_ru", sa.String(255), nullable=False),
        sa.Column("name_uz_latn", sa.String(255)),
        sa.Column("name_uz_cyrl", sa.String(255)),
        sa.Column("keywords_ru", postgresql.ARRAY(sa.Text())),
        sa.Column("keywords_uz", postgresql.ARRAY(sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("categories.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "uom",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name_ru", sa.String(100)),
        sa.Column("base_unit", sa.String(20)),
        sa.Column("factor", sa.Numeric(18, 6)),
    )
    op.create_index("uq_uom_code", "uom", ["code"], unique=True)

    op.create_table(
        "package_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name_ru", sa.String(255)),
    )
    op.create_index("uq_package_types_code", "package_types", ["code"], unique=True)

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    op.create_table(
        "products",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
        # Names
        sa.Column("name_raw", sa.Text()),
        sa.Column("name_normalized", sa.Text()),
        sa.Column("name_canonical", sa.Text()),
        sa.Column("name_pos", sa.String(20)),
        sa.Column("name_receipt", sa.String(40)),
        sa.Column("name_catalog", sa.Text()),
        sa.Column("name_erp", sa.Text()),
        # Brand / manufacturer
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id")),
        sa.Column("brand_name", sa.String(255)),
        sa.Column("manufacturer_id", sa.Integer(), sa.ForeignKey("manufacturers.id")),
        sa.Column("subbrand", sa.String(255)),
        # Classification
        sa.Column("product_type_id", sa.Integer(), sa.ForeignKey("product_types.id")),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id")),
        sa.Column("variant", sa.String(255)),
        # Quantity
        sa.Column("quantity_value", sa.Numeric(12, 4)),
        sa.Column("quantity_unit", sa.String(20)),
        sa.Column("base_quantity", sa.Numeric(12, 4)),
        sa.Column("base_unit", sa.String(20)),
        sa.Column("sale_unit", sa.String(20)),
        # Package
        sa.Column("package_code", sa.String(50)),
        # MXIK (dangerous — manual only)
        sa.Column("mxik_code", sa.String(17)),
        sa.Column("mxik_package_code", sa.Integer()),
        sa.Column("mxik_is_group_code", sa.Boolean(), server_default="false"),
        sa.Column("mxik_confidence", sa.Numeric(4, 3)),
        # Fiscal flags (dangerous — manual only)
        sa.Column("label_required", sa.SmallInteger()),
        sa.Column("label_for_check", sa.SmallInteger()),
        sa.Column("cash_sale", sa.SmallInteger()),
        # Quality
        sa.Column("quality_status", sa.String(20)),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.Column("completeness_score", sa.Numeric(4, 3)),
        sa.Column("issues", postgresql.ARRAY(sa.Text())),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("review_reasons", postgresql.ARRAY(sa.Text())),
        sa.Column("field_sources", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_products_status", "products", ["status"])
    op.create_index("ix_products_mxik_code", "products", ["mxik_code"])
    op.create_index("ix_products_review_required", "products", ["review_required"])
    op.create_index(
        "ix_products_name_canonical_trgm",
        "products",
        ["name_canonical"],
        postgresql_using="gin",
        postgresql_ops={"name_canonical": "gin_trgm_ops"},
    )

    op.create_table(
        "product_barcodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False),
        sa.Column("barcode", sa.String(50), nullable=False),
        sa.Column("barcode_type", sa.String(20), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_product_barcodes_product_id", "product_barcodes", ["product_id"])
    op.create_index("ix_product_barcodes_barcode", "product_barcodes", ["barcode"])

    # ------------------------------------------------------------------
    # Input data
    # ------------------------------------------------------------------
    op.create_table(
        "raw_input_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(50)),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_raw_input_log_source_id", "raw_input_log", ["source_id"])
    op.create_index("ix_raw_input_log_status", "raw_input_log", ["status"])

    op.create_table(
        "external_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("code", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_external_codes_product_id", "external_codes", ["product_id"])

    # ------------------------------------------------------------------
    # Quality management
    # ------------------------------------------------------------------
    op.create_table(
        "operator_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("operator_id", sa.String(100), nullable=False),
        sa.Column("decision_type", sa.String(30), nullable=False),
        sa.Column("field_name", sa.String(100)),
        sa.Column("old_value", postgresql.JSONB()),
        sa.Column("new_value", postgresql.JSONB()),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_operator_decisions_product_id", "operator_decisions", ["product_id"])

    op.create_table(
        "conflicts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("existing_value", postgresql.JSONB()),
        sa.Column("incoming_value", postgresql.JSONB()),
        sa.Column("source_id", sa.String(100)),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_by", sa.String(100)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conflicts_product_id", "conflicts", ["product_id"])

    op.create_table(
        "quality_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_products", sa.Integer()),
        sa.Column("with_brand", sa.Integer()),
        sa.Column("with_mxik", sa.Integer()),
        sa.Column("with_barcode", sa.Integer()),
        sa.Column("auto_confirmed", sa.Integer()),
        sa.Column("review_queue_size", sa.Integer()),
        sa.Column("avg_confidence", sa.Numeric(4, 3)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    op.create_table(
        "product_type_mxik_map",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_type_id", sa.Integer(), sa.ForeignKey("product_types.id"), nullable=False),
        sa.Column("mxik_group_code", sa.String(17), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # search_vector trigger for mxik_catalog
    op.execute("""
        CREATE FUNCTION mxik_catalog_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('russian', coalesce(NEW.mxik_name_ru, '')), 'A') ||
                setweight(to_tsvector('simple',  coalesce(NEW.mxik_name_lat, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER mxik_catalog_search_vector_trigger
        BEFORE INSERT OR UPDATE ON mxik_catalog
        FOR EACH ROW EXECUTE FUNCTION mxik_catalog_search_vector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS mxik_catalog_search_vector_trigger ON mxik_catalog")
    op.execute("DROP FUNCTION IF EXISTS mxik_catalog_search_vector_update")

    op.drop_table("product_type_mxik_map")
    op.drop_table("quality_stats")
    op.drop_table("conflicts")
    op.drop_table("operator_decisions")
    op.drop_table("external_codes")
    op.drop_table("raw_input_log")
    op.drop_table("product_barcodes")
    op.drop_table("products")
    op.drop_table("package_types")
    op.drop_table("uom")
    op.drop_table("categories")
    op.drop_table("product_types")
    op.drop_table("brand_aliases")
    op.drop_table("brands")
    op.drop_table("manufacturers")
    op.drop_table("mxik_sync_log")
    op.drop_table("mxik_packages")
    op.drop_table("mxik_catalog")
