"""GET/POST /api/v1/review — очередь ревью и решения операторов."""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import ExternalCode, MxikCatalog, OperatorDecision, Product, ProductBarcode, ProductTypeMxikMap
from product_db.models.schemas import ApiResponse, ProductResponse
from product_db.pipeline.learner import learn_from_decision
from product_db.pipeline.quality import _CONFIDENCE_PENALTIES, _COMPLETENESS_PENALTIES

router = APIRouter(prefix="/review", tags=["review"])


class DecideRequest(BaseModel):
    decision_type: str
    field_name: str | None = None
    new_value: dict | None = None
    comment: str | None = None


class BatchDecideRequest(BaseModel):
    product_ids: list[str]
    decision_type: str  # confirm_product | dismiss | set_type | set_category
    value: int | None = None  # product_type_id или category_id для set_type/set_category


@router.post("/batch", response_model=ApiResponse)
async def batch_decide(
    req: BatchDecideRequest,
    x_operator_id: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Массовые решения: confirm_product или dismiss (убрать из очереди)."""
    if not req.product_ids:
        return ApiResponse(data={"processed": 0})

    ids = [uuid.UUID(pid) for pid in req.product_ids]

    if req.decision_type == "dismiss":
        await db.execute(
            update(Product)
            .where(Product.product_id.in_(ids))
            .values(review_required=False)
        )
        for pid in ids:
            db.add(OperatorDecision(
                product_id=pid,
                operator_id=x_operator_id,
                decision_type="dismiss",
            ))
    elif req.decision_type == "confirm_product":
        result = await db.execute(select(Product).where(Product.product_id.in_(ids)))
        products = result.scalars().all()
        for product in products:
            clean_issues = product.issues or []
            if product.brand_id or product.brand_name:
                clean_issues = [i for i in clean_issues if i != "MISSING_BRAND"]
            if product.product_type_id:
                clean_issues = [i for i in clean_issues if i != "MISSING_PRODUCT_TYPE"]
            if product.mxik_code:
                clean_issues = [i for i in clean_issues if i not in ("MISSING_MXIK", "MXIK_GROUP_CODE")]
            confidence = round(max(0.0, 1.0 - sum(_CONFIDENCE_PENALTIES.get(i, 0) for i in clean_issues)), 3)
            completeness = round(max(0.0, 1.0 - sum(_COMPLETENESS_PENALTIES.get(i, 0) for i in clean_issues)), 3)
            await db.execute(
                update(Product)
                .where(Product.product_id == product.product_id)
                .values(
                    status="certified",
                    review_required=False,
                    issues=clean_issues,
                    confidence_score=confidence,
                    completeness_score=completeness,
                )
            )
            db.add(OperatorDecision(
                product_id=product.product_id,
                operator_id=x_operator_id,
                decision_type="confirm_product",
            ))

    elif req.decision_type == "set_type" and req.value is not None:
        await db.execute(
            update(Product)
            .where(Product.product_id.in_(ids))
            .values(
                product_type_id=req.value,
                issues=func.array_remove(Product.issues, "MISSING_PRODUCT_TYPE"),
            )
        )
        for pid in ids:
            db.add(OperatorDecision(
                product_id=pid,
                operator_id=x_operator_id,
                decision_type="correct_field",
                field_name="product_type_id",
                new_value={"product_type_id": req.value},
            ))
    elif req.decision_type == "set_category" and req.value is not None:
        await db.execute(
            update(Product)
            .where(Product.product_id.in_(ids))
            .values(category_id=req.value)
        )
        for pid in ids:
            db.add(OperatorDecision(
                product_id=pid,
                operator_id=x_operator_id,
                decision_type="correct_field",
                field_name="category_id",
                new_value={"category_id": req.value},
            ))

    await db.commit()
    return ApiResponse(data={"processed": len(ids)})


_SORT_COLUMNS = {
    "confidence": Product.confidence_score,
    "name": Product.name_canonical,
    "brand": Product.brand_name,
    "created": Product.created_at,
}


@router.get("/queue", response_model=ApiResponse)
async def review_queue(
    offset: int = 0,
    limit: int = 50,
    sort_by: str = "confidence",
    sort_dir: str = "asc",
    product_type_id: int | None = None,
    category_id: int | None = None,
    no_category: bool = False,
    no_type: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Очередь товаров на ревью."""
    from sqlalchemy import func
    base_where = [Product.review_required.is_(True), Product.status != "merged"]
    if product_type_id:
        base_where.append(Product.product_type_id == product_type_id)
    if category_id:
        base_where.append(Product.category_id == category_id)
    if no_category:
        base_where.append(Product.category_id.is_(None))
    if no_type:
        base_where.append(Product.product_type_id.is_(None))

    total = await db.scalar(
        select(func.count(Product.product_id)).where(*base_where)
    )
    col = _SORT_COLUMNS.get(sort_by, Product.confidence_score)
    order = col.asc() if sort_dir != "desc" else col.desc()
    result = await db.execute(
        select(Product)
        .where(*base_where)
        .order_by(order, Product.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    items = result.scalars().all()
    items_data = []
    for p in items:
        d = {k: v for k, v in p.__dict__.items() if not k.startswith('_')}
        d['barcodes'] = []
        items_data.append(ProductResponse.model_validate(d).model_dump())
    return ApiResponse(data={
        "items": items_data,
        "total": total or 0,
        "offset": offset,
        "limit": limit,
    })


@router.get("/{product_id}/decisions", response_model=ApiResponse)
async def product_decisions(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """История решений оператора по товару."""
    result = await db.execute(
        select(OperatorDecision)
        .where(OperatorDecision.product_id == product_id)
        .order_by(OperatorDecision.created_at.desc())
        .limit(50)
    )
    decisions = result.scalars().all()
    return ApiResponse(data=[
        {
            "id": str(d.id),
            "operator_id": d.operator_id,
            "decision_type": d.decision_type,
            "field_name": d.field_name,
            "new_value": d.new_value,
            "comment": d.comment,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in decisions
    ])


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

    bc_result = await db.execute(
        select(ProductBarcode.barcode).where(ProductBarcode.product_id == product_id)
    )
    barcodes = [row.barcode for row in bc_result.all()]
    product_dict = {k: v for k, v in product.__dict__.items() if not k.startswith('_')}
    product_dict['barcodes'] = barcodes

    return ApiResponse(data={
        "product": ProductResponse.model_validate(product_dict).model_dump(),
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
        # Убираем ишью которые больше не актуальны
        clean_issues = product.issues or []
        if product.brand_id or product.brand_name:
            clean_issues = [i for i in clean_issues if i != "MISSING_BRAND"]
        if product.product_type_id:
            clean_issues = [i for i in clean_issues if i != "MISSING_PRODUCT_TYPE"]
        if product.mxik_code:
            clean_issues = [i for i in clean_issues if i not in ("MISSING_MXIK", "MXIK_GROUP_CODE")]
        confidence = round(max(0.0, 1.0 - sum(_CONFIDENCE_PENALTIES.get(i, 0) for i in clean_issues)), 3)
        completeness = round(max(0.0, 1.0 - sum(_COMPLETENESS_PENALTIES.get(i, 0) for i in clean_issues)), 3)
        await db.execute(
            update(Product)
            .where(Product.product_id == product_id)
            .values(
                status="certified",
                review_required=False,
                issues=clean_issues,
                confidence_score=confidence,
                completeness_score=completeness,
            )
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
            values = dict(req.new_value)
            # Подтягиваем фискальные поля из каталога ИКПУ
            mxik_code = values.get("mxik_code")
            if mxik_code:
                mxik_row = await db.execute(
                    select(MxikCatalog).where(MxikCatalog.mxik == mxik_code)
                )
                mxik_obj = mxik_row.scalar_one_or_none()
                if mxik_obj:
                    values["label_required"] = mxik_obj.label
                    values["label_for_check"] = mxik_obj.label_for_check
                    values["cash_sale"] = mxik_obj.cash_sale
                    values["mxik_is_group_code"] = mxik_obj.is_group_code
            await db.execute(
                update(Product)
                .where(Product.product_id == product_id)
                .values(**values)
            )
    elif req.decision_type == "merge_products":
        if req.new_value and req.new_value.get("target_product_id"):
            target_id = uuid.UUID(req.new_value["target_product_id"])
            # Переносим штрихкоды на целевой товар
            await db.execute(
                update(ProductBarcode)
                .where(ProductBarcode.product_id == product_id)
                .values(product_id=target_id)
            )
            # Переносим внешние коды
            await db.execute(
                update(ExternalCode)
                .where(ExternalCode.product_id == product_id)
                .values(product_id=target_id)
            )
            # Помечаем дубль как слитый, убираем из очереди
            await db.execute(
                update(Product)
                .where(Product.product_id == product_id)
                .values(status="merged", review_required=False)
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

    # Обновляем карту MXIK если подтверждён товар с типом и конкретным ИКПУ
    if req.decision_type == "confirm_product" and product.product_type_id and product.mxik_code:
        mxik_obj = await db.scalar(
            select(MxikCatalog).where(MxikCatalog.mxik == product.mxik_code)
        )
        if mxik_obj:
            group_code = product.mxik_code if mxik_obj.is_group_code else product.mxik_code[:8] + "000000"
            # Ищем существующую запись в карте
            existing = await db.scalar(
                select(ProductTypeMxikMap).where(
                    ProductTypeMxikMap.product_type_id == product.product_type_id
                )
            )
            if existing:
                # Обновляем только если новый код надёжнее (не группа > группа)
                if not mxik_obj.is_group_code:
                    existing.mxik_group_code = group_code
                    existing.confidence = min(float(existing.confidence or 0.5) + 0.05, 1.0)
            else:
                db.add(ProductTypeMxikMap(
                    product_type_id=product.product_type_id,
                    mxik_group_code=group_code,
                    confidence=0.7,
                ))

    await db.commit()

    return ApiResponse(data={"decision_id": str(decision.id)})
