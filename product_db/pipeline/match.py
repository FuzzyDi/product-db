"""Step 5: поиск/создание товара в базе."""
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import Product, ProductBarcode
from .context import PipelineContext
from .barcode import GLOBAL_TYPES

FUZZY_MATCH_THRESHOLD = 0.75  # pg_trgm similarity


async def _find_by_barcode(session: AsyncSession, barcode: str) -> uuid.UUID | None:
    result = await session.execute(
        select(ProductBarcode.product_id).where(ProductBarcode.barcode == barcode).limit(1)
    )
    row = result.first()
    return row.product_id if row else None


async def _find_by_normalized_name(session: AsyncSession, name: str) -> uuid.UUID | None:
    result = await session.execute(
        select(Product.product_id).where(Product.name_normalized == name).limit(1)
    )
    row = result.first()
    return row.product_id if row else None


async def _find_by_fuzzy_name(
    session: AsyncSession, name: str
) -> tuple[uuid.UUID | None, float]:
    """Поиск через pg_trgm similarity. Возвращает (product_id, score)."""
    if not name or len(name) < 4:
        return None, 0.0
    result = await session.execute(
        text(
            """
            SELECT product_id, similarity(name_normalized, :name) AS sim
            FROM products
            WHERE name_normalized % :name
            ORDER BY sim DESC
            LIMIT 1
            """
        ),
        {"name": name},
    )
    row = result.first()
    if row and row.sim >= FUZZY_MATCH_THRESHOLD:
        return row.product_id, float(row.sim)
    return None, 0.0


async def _create_candidate(session: AsyncSession, ctx: PipelineContext) -> uuid.UUID:
    product_id = uuid.uuid4()
    product = Product(
        product_id=product_id,
        status="candidate",
        name_raw=ctx.name_raw,
        name_normalized=ctx.name_normalized,
        brand_id=ctx.brand_id,
        brand_name=ctx.brand_name,
        product_type_id=ctx.product_type_id,
        quantity_value=ctx.quantity_value,
        quantity_unit=ctx.quantity_unit,
        package_code=ctx.package_code,
        field_sources=ctx.field_sources,
    )
    session.add(product)

    if ctx.barcode and ctx.barcode_type in GLOBAL_TYPES:
        session.add(ProductBarcode(
            product_id=product_id,
            barcode=ctx.barcode,
            barcode_type=ctx.barcode_type,
            is_primary=True,
        ))

    await session.flush()
    return product_id


async def run(ctx: PipelineContext, session: AsyncSession) -> PipelineContext:
    product_id = None

    # 1. По глобальному штрихкоду (точное совпадение)
    if ctx.barcode and ctx.barcode_type in GLOBAL_TYPES:
        product_id = await _find_by_barcode(session, ctx.barcode)

    # 2. По нормализованному имени (точное совпадение)
    if product_id is None and ctx.name_normalized:
        product_id = await _find_by_normalized_name(session, ctx.name_normalized)

    # 3. Нечёткое совпадение по имени (pg_trgm)
    if product_id is None and ctx.name_normalized:
        product_id, sim = await _find_by_fuzzy_name(session, ctx.name_normalized)
        if product_id:
            ctx.issues.append("FUZZY_MATCH")
            ctx.field_sources["match"] = f"fuzzy:{sim:.2f}"

    # 4. Создаём кандидата
    if product_id is None:
        product_id = await _create_candidate(session, ctx)
        ctx.is_new = True

    ctx.product_id = product_id
    return ctx
