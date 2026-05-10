"""Step 9: маршрутизация — авто-подтверждение или очередь ревью."""
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import Product
from .context import PipelineContext
from .quality import CRITICAL_ISSUES

AUTO_CONFIRM_THRESHOLD = 0.85


async def run(ctx: PipelineContext, session: AsyncSession) -> PipelineContext:
    has_critical = any(i in CRITICAL_ISSUES for i in ctx.issues)
    auto = (
        ctx.confidence_score >= AUTO_CONFIRM_THRESHOLD
        and not has_critical
        and not ctx.mxik_is_group_code
    )

    if auto:
        new_status = "verified"
        review_required = False
    else:
        new_status = "draft"
        review_required = True
        if not ctx.review_reasons:
            ctx.review_reasons.append("LOW_CONFIDENCE")

    ctx.review_required = review_required

    await session.execute(
        update(Product)
        .where(Product.product_id == ctx.product_id)
        .values(
            status=new_status,
            name_normalized=ctx.name_normalized,
            name_canonical=ctx.name_canonical,
            name_pos=ctx.name_pos,
            name_receipt=ctx.name_receipt,
            name_catalog=ctx.name_catalog,
            brand_id=ctx.brand_id,
            brand_name=ctx.brand_name,
            product_type_id=ctx.product_type_id,
            quantity_value=ctx.quantity_value,
            quantity_unit=ctx.quantity_unit,
            package_code=ctx.package_code,
            mxik_code=ctx.mxik_code,
            mxik_package_code=ctx.mxik_package_code,
            mxik_is_group_code=ctx.mxik_is_group_code,
            mxik_confidence=ctx.mxik_confidence,
            confidence_score=ctx.confidence_score,
            completeness_score=ctx.completeness_score,
            issues=ctx.issues,
            review_required=review_required,
            review_reasons=ctx.review_reasons,
            field_sources=ctx.field_sources,
        )
    )
    return ctx
