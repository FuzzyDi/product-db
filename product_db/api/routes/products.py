"""GET/PUT /api/v1/products — каталог товаров."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import Product, ProductBarcode
from product_db.models.schemas import (
    ApiResponse,
    ProductListResponse,
    ProductResponse,
    ProductUpdateRequest,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ApiResponse)
async def list_products(
    status: str | None = None,
    brand_id: int | None = None,
    product_type_id: int | None = None,
    review_required: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Product)
    if status:
        q = q.where(Product.status == status)
    if brand_id is not None:
        q = q.where(Product.brand_id == brand_id)
    if product_type_id is not None:
        q = q.where(Product.product_type_id == product_type_id)
    if review_required is not None:
        q = q.where(Product.review_required.is_(review_required))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(q.order_by(Product.created_at.desc()).offset(offset).limit(limit))
    items = result.scalars().all()

    data = ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in items],
        total=total or 0,
        offset=offset,
        limit=limit,
    )
    return ApiResponse(data=data.model_dump())


@router.get("/search", response_model=ApiResponse)
async def search_products(
    q: str = Query(..., min_length=2),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Полнотекстовый + trigram поиск по name_canonical и name_normalized."""
    result = await db.execute(
        text(
            """
            SELECT p.*,
                   similarity(p.name_canonical, :q) AS sim
            FROM products p
            WHERE p.name_canonical % :q
               OR p.name_normalized ILIKE :like
            ORDER BY sim DESC, p.created_at DESC
            OFFSET :offset LIMIT :limit
            """
        ),
        {"q": q, "like": f"%{q.lower()}%", "offset": offset, "limit": limit},
    )
    rows = result.mappings().all()
    items = [ProductResponse.model_validate(dict(r)) for r in rows]
    return ApiResponse(data={"items": [i.model_dump() for i in items], "count": len(items)})


@router.get("/{product_id}", response_model=ApiResponse)
async def get_product(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Not found")
    return ApiResponse(data=ProductResponse.model_validate(product).model_dump())


@router.put("/{product_id}", response_model=ApiResponse)
async def update_product(
    product_id: uuid.UUID,
    req: ProductUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.product_id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Not found")

    values = req.model_dump(exclude_none=True)
    if values:
        await db.execute(update(Product).where(Product.product_id == product_id).values(**values))
        await db.commit()
        await db.refresh(product)

    return ApiResponse(data=ProductResponse.model_validate(product).model_dump())
