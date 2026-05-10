"""GET/POST /api/v1/review — очередь ревью и решения операторов."""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import MxikCatalog, OperatorDecision, Product
from product_db.models.schemas import ApiResponse, ProductResponse
from product_db.pipeline.learner import learn_from_decision

router = APIRouter(prefix="/review", tags=["review"])


class DecideRequest(BaseModel):
    decision_type: str
    field_name: str | None = None
    new_value: dict | None = None
    comment: str | None = None


@router.get("/queue", response_model=ApiResponse)
async def review_queue(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Очередь товаров на ревью, отсортированная по confidence ASC."""
    from sqlalchemy import func
    total = await db.scalar(
        select(func.count(Product.product_id)).where(Product.review_required.is_(True))
    )
    result = await db.execute(
        select(Product)
        .where(Product.review_required.is_(True))
        .order_by(Product.confidence_score.asc(), Product.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    items = result.scalars().all()
    return ApiResponse(data={
        "items": [ProductResponse.model_validate(p).model_dump() for p in items],
        "total": total or 0,
        "offset": offset,
        "limit": limit,
    })


@router.get("/{product_id}", response_model=ApiResponse)
async def review_detail(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Контекст для оператора: карточка + кандидаты ИКПУ + похожие товары."""
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Not found")

    # Кандидаты ИКПУ по штрихкоду или тексту
    mxik_candidates = []
    if product.name_canonical:
        words = [w for w in (product.name_canonical or "").split() if len(w) > 2]
        if words:
            q = " | ".join(words[:5])
            mxik_result = await db.execute(
                text(
                    """
                    SELECT mxik, mxik_name_ru, international_code,
                           ts_rank(search_vector, to_tsquery('russian', :q)) AS rank
                    FROM mxik_catalog
                    WHERE search_vector @@ to_tsquery('russian', :q)
                      AND is_active = true
                    ORDER BY rank DESC
                    LIMIT 5
                    """
                ),
                {"q": q},
            )
            mxik_candidates = [dict(r) for r in mxik_result.mappings().all()]

    # Похожие товары (для проверки дублей)
    similar = []
    if product.name_canonical:
        sim_result = await db.execute(
            text(
                """
                SELECT product_id::text, name_canonical, brand_name,
                       similarity(name_canonical, :name) AS sim
                FROM products
                WHERE name_canonical % :name
                  AND product_id != :pid
                ORDER BY sim DESC
                LIMIT 5
                """
            ),
            {"name": product.name_canonical, "pid": str(product_id)},
        )
        similar = [dict(r) for r in sim_result.mappings().all()]

    return ApiResponse(data={
        "product": ProductResponse.model_validate(product).model_dump(),
        "mxik_candidates": mxik_candidates,
        "similar_products": similar,
    })


@router.post("/{product_id}/decide", response_model=ApiResponse)
async def decide(
    product_id: uuid.UUID,
    req: DecideRequest,
    x_operator_id: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Not found")

    # Фиксируем решение
    decision = OperatorDecision(
        product_id=product_id,
        operator_id=x_operator_id,
        decision_type=req.decision_type,
        field_name=req.field_name,
        old_value={req.field_name: getattr(product, req.field_name, None)} if req.field_name else None,
        new_value=req.new_value,
        comment=req.comment,
    )
    db.add(decision)

    # Применяем безопасные изменения
    _SAFE_FIELDS = {
        "name_canonical", "name_pos", "name_receipt",
        "variant", "package_code", "category_id",
        "brand_id", "brand_name", "product_type_id",
    }
    _DANGEROUS_FIELDS = {
        "mxik_code", "mxik_package_code", "label_required",
        "label_for_check", "cash_sale",
    }

    if req.decision_type == "confirm_product":
        await db.execute(
            update(Product)
            .where(Product.product_id == product_id)
            .values(status="certified", review_required=False)
        )
    elif req.decision_type == "correct_field" and req.field_name and req.new_value:
        if req.field_name in _SAFE_FIELDS:
            field_val = req.new_value.get(req.field_name)
            await db.execute(
                update(Product)
                .where(Product.product_id == product_id)
                .values(**{req.field_name: field_val})
            )
        elif req.field_name in _DANGEROUS_FIELDS:
            # Опасные поля — только через оператора, применяем напрямую
            field_val = req.new_value.get(req.field_name)
            await db.execute(
                update(Product)
                .where(Product.product_id == product_id)
                .values(**{req.field_name: field_val})
            )
    elif req.decision_type in ("confirm_mxik", "confirm_package_code"):
        if req.new_value:
            await db.execute(
                update(Product)
                .where(Product.product_id == product_id)
                .values(**req.new_value)
            )
    elif req.decision_type == "reject_match":
        await db.execute(
            update(Product)
            .where(Product.product_id == product_id)
            .values(status="candidate", review_required=True)
        )

    await db.commit()

    # Обучаем систему на основе решения (синхронно, быстро)
    await db.refresh(product)
    await learn_from_decision(db, decision, product)
    await db.commit()

    return ApiResponse(data={"decision_id": str(decision.id)})
