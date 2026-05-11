"""Step 9: маршрутизация — авто-подтверждение или очередь ревью."""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import Product
from .context import PipelineContext
from .quality import CRITICAL_ISSUES

AUTO_CONFIRM_THRESHOLD = 0.85

# Поля установленные оператором — пайплайн не перезаписывает их у существующих товаров
_OPERATOR_FIELDS = {"brand_id", "brand_name", "product_type_id", "mxik_code", "mxik_package_code", "mxik_is_group_code"}
# Статусы выше которых пайплайн не опускает
_PROTECTED_STATUSES = {"certified"}


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

    values: dict = {
        "name_normalized": ctx.name_normalized,
        "name_canonical": ctx.name_canonical,
        "name_pos": ctx.name_pos,
        "name_receipt": ctx.name_receipt,
        "name_catalog": ctx.name_catalog,
        "brand_id": ctx.brand_id,
        "brand_name": ctx.brand_name,
        "product_type_id": ctx.product_type_id,
        "quantity_value": ctx.quantity_value,
        "quantity_unit": ctx.quantity_unit,
        "package_code": ctx.package_code,
        "mxik_code": ctx.mxik_code,
        "mxik_package_code": ctx.mxik_package_code,
        "mxik_is_group_code": ctx.mxik_is_group_code,
        "mxik_confidence": ctx.mxik_confidence,
        "confidence_score": ctx.confidence_score,
        "completeness_score": ctx.completeness_score,
        "issues": ctx.issues,
        "review_required": review_required,
        "review_reasons": ctx.review_reasons,
        "field_sources": ctx.field_sources,
        "status": new_status,
    }

    if not ctx.is_new:
        # Существующий товар: защищаем оператор-установленные поля
        result = await session.execute(
            select(Product).where(Product.product_id == ctx.product_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            # Не опускаем certified/verified ниже
            if existing.status in _PROTECTED_STATUSES:
                values["status"] = existing.status
                values["review_required"] = False
                ctx.review_required = False

            # Не перезаписываем поля, уже установленные оператором
            for field in _OPERATOR_FIELDS:
                if getattr(existing, field, None) is not None:
                    values.pop(field, None)

    await session.execute(
        update(Product)
        .where(Product.product_id == ctx.product_id)
        .values(**values)
    )
    return ctx
