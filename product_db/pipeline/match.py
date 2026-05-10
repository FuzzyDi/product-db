"""Step 5: поиск/создание товара в базе."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import Product, ProductBarcode
from .context import PipelineContext


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

    if ctx.barcode and ctx.barcode_type:
        from product_db.pipeline.barcode import GLOBAL_TYPES
        barcode = ProductBarcode(
            product_id=product_id,
            barcode=ctx.barcode,
            barcode_type=ctx.barcode_type,
            is_primary=ctx.barcode_type in GLOBAL_TYPES,
        )
        session.add(barcode)

    await session.flush()
    return product_id


async def run(ctx: PipelineContext, session: AsyncSession) -> PipelineContext:
    product_id = None

    # 1. По штрихкоду (только глобальные)
    from product_db.pipeline.barcode import GLOBAL_TYPES
    if ctx.barcode and ctx.barcode_type in GLOBAL_TYPES:
        product_id = await _find_by_barcode(session, ctx.barcode)

    # 2. По нормализованному имени
    if product_id is None and ctx.name_normalized:
        product_id = await _find_by_normalized_name(session, ctx.name_normalized)

    # 3. Создаём кандидата
    if product_id is None:
        product_id = await _create_candidate(session, ctx)
        ctx.is_new = True

    ctx.product_id = product_id
    return ctx
