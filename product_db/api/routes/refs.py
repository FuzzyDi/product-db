"""GET/POST /api/v1/refs — справочники."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import Brand, BrandAlias, Category, PackageType, Product, ProductType, UOM
from product_db.models.schemas import ApiResponse
from product_db.nlp.fuzzy import find_best_brand
from product_db.pipeline.generate import build_canonical

router = APIRouter(prefix="/refs", tags=["refs"])


# --------------------------------------------------------------------------
# Brands
# --------------------------------------------------------------------------

class BrandCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    manufacturer_id: int | None = None


class BrandAliasRequest(BaseModel):
    alias: str = Field(..., min_length=1, max_length=255)


class BrandAliasBatchRequest(BaseModel):
    aliases: list[str] = Field(..., min_length=1)


@router.get("/brands/unrecognized", response_model=ApiResponse)
async def unrecognized_brands(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Токены из имён товаров без бренда, отсортированные по частоте."""
    import re
    from collections import Counter
    from sqlalchemy import text as sa_text

    # Стоп-слова: единицы измерения, предлоги, числа, мусор
    STOP = {
        "мл", "л", "г", "кг", "гр", "шт", "уп", "пак", "мг", "oz", "ml", "gr", "kg", "lt",
        "the", "and", "for", "без", "для", "при", "или", "это", "как", "что", "все",
        "от", "до", "из", "по", "на", "не", "то", "со", "во", "же", "ли", "бы",
        "x", "n", "в", "с", "к", "а", "и", "о", "у", "я",
    }

    result = await db.execute(
        sa_text(
            """
            SELECT name_normalized
            FROM products
            WHERE review_required = true
              AND 'MISSING_BRAND' = ANY(issues)
              AND name_normalized IS NOT NULL
            LIMIT 2000
            """
        )
    )
    names = [row.name_normalized for row in result.all()]

    counter: Counter = Counter()
    for name in names:
        tokens = re.split(r'[\s\-_/\\|.,;:!?()\[\]{}«»"\']+', name.lower())
        for token in tokens:
            token = token.strip()
            # Пропускаем: короткие, числа, стоп-слова
            if len(token) < 3:
                continue
            if re.fullmatch(r'[\d.,]+', token):
                continue
            if re.match(r'\d', token):  # начинается с цифры (400гр, 1л и т.п.)
                continue
            if token in STOP:
                continue
            counter[token] += 1

    top = counter.most_common(limit)
    return ApiResponse(data=[{"token": t, "count": c} for t, c in top])


@router.get("/brands", response_model=ApiResponse)
async def list_brands(
    q: str | None = None,
    offset: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Brand)
    if q:
        stmt = stmt.where(Brand.name_canonical.ilike(f"%{q}%"))
    result = await db.execute(stmt.order_by(Brand.name_canonical).offset(offset).limit(limit))
    brands = result.scalars().all()

    # Загружаем алиасы для всех брендов одним запросом
    brand_ids = [b.id for b in brands]
    aliases_by_brand: dict[int, list[str]] = {b.id: [] for b in brands}
    if brand_ids:
        alias_result = await db.execute(
            select(BrandAlias.brand_id, BrandAlias.alias)
            .where(BrandAlias.brand_id.in_(brand_ids))
            .order_by(BrandAlias.alias)
        )
        for row in alias_result.all():
            aliases_by_brand[row.brand_id].append(row.alias)

    return ApiResponse(data=[
        {
            "id": b.id,
            "name_canonical": b.name_canonical,
            "manufacturer_id": b.manufacturer_id,
            "aliases": aliases_by_brand[b.id],
        }
        for b in brands
    ])


@router.post("/brands", response_model=ApiResponse)
async def create_brand(req: BrandCreateRequest, db: AsyncSession = Depends(get_db)):
    canonical = req.name.strip().upper()
    existing = await db.scalar(select(Brand).where(Brand.name_canonical == canonical))
    if existing:
        raise HTTPException(status_code=409, detail="Brand already exists")
    brand = Brand(name_canonical=canonical, manufacturer_id=req.manufacturer_id)
    db.add(brand)
    await db.flush()
    # Canonical как первый alias
    db.add(BrandAlias(brand_id=brand.id, alias=canonical, source="operator"))
    await db.commit()
    return ApiResponse(data={"id": brand.id, "name_canonical": brand.name_canonical})


@router.post("/brands/reprocess", response_model=ApiResponse)
async def reprocess_brands(db: AsyncSession = Depends(get_db)):
    """Перезапускает распознавание бренда для товаров с brand_id IS NULL."""
    # Загружаем алиасы
    alias_result = await db.execute(
        select(BrandAlias.alias, BrandAlias.brand_id, Brand.name_canonical)
        .join(Brand, Brand.id == BrandAlias.brand_id)
    )
    aliases = [(row.alias, row.brand_id, row.name_canonical) for row in alias_result.all()]

    # Загружаем типы товаров для rebuild canonical
    pt_result = await db.execute(select(ProductType.id, ProductType.name_ru))
    type_map = {row.id: row.name_ru for row in pt_result.all()}

    # Загружаем товары без бренда
    products_result = await db.execute(
        select(Product).where(Product.brand_id.is_(None))
    )
    products = products_result.scalars().all()

    updated = 0
    for p in products:
        if not p.name_raw:
            continue
        brand_id, brand_name, score = find_best_brand(p.name_raw, aliases)
        if not brand_id:
            continue
        product_type_name = type_map.get(p.product_type_id) if p.product_type_id else None
        new_canonical = build_canonical(
            product_type=product_type_name,
            brand=brand_name,
            subbrand=None,
            variant=None,
            quantity_value=p.quantity_value,
            quantity_unit=p.quantity_unit,
            package_code=p.package_code,
            name_raw=p.name_raw,
        )
        await db.execute(
            update(Product)
            .where(Product.product_id == p.product_id)
            .values(
                brand_id=brand_id,
                brand_name=brand_name,
                name_canonical=new_canonical,
                name_pos=new_canonical[:20],
                name_receipt=new_canonical[:40],
                issues=func.array_remove(Product.issues, 'MISSING_BRAND'),
            )
        )
        updated += 1

    await db.commit()
    return ApiResponse(data={"updated": updated, "checked": len(products)})


@router.post("/brands/{brand_id}/aliases", response_model=ApiResponse)
async def add_alias(brand_id: int, req: BrandAliasRequest, db: AsyncSession = Depends(get_db)):
    brand = await db.scalar(select(Brand).where(Brand.id == brand_id))
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    alias = BrandAlias(brand_id=brand_id, alias=req.alias.strip(), source="operator")
    db.add(alias)
    await db.commit()
    return ApiResponse(data={"brand_id": brand_id, "alias": alias.alias})


@router.post("/brands/{brand_id}/aliases/batch", response_model=ApiResponse)
async def add_aliases_batch(brand_id: int, req: BrandAliasBatchRequest, db: AsyncSession = Depends(get_db)):
    brand = await db.scalar(select(Brand).where(Brand.id == brand_id))
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Существующие алиасы чтобы не дублировать
    existing_result = await db.execute(
        select(BrandAlias.alias).where(BrandAlias.brand_id == brand_id)
    )
    existing = {row.alias for row in existing_result.all()}

    added = []
    for raw in req.aliases:
        alias_str = raw.strip()
        if alias_str and alias_str not in existing:
            db.add(BrandAlias(brand_id=brand_id, alias=alias_str, source="operator"))
            existing.add(alias_str)
            added.append(alias_str)

    await db.commit()
    return ApiResponse(data={"brand_id": brand_id, "added": added, "count": len(added)})


# --------------------------------------------------------------------------
# Product types
# --------------------------------------------------------------------------

@router.get("/product-types", response_model=ApiResponse)
async def list_product_types(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductType).order_by(ProductType.name_ru))
    types = result.scalars().all()
    return ApiResponse(data=[
        {
            "id": t.id,
            "name_ru": t.name_ru,
            "name_uz_latn": t.name_uz_latn,
            "keywords_ru": t.keywords_ru,
        }
        for t in types
    ])


# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------

class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    parent_id: int | None = None


@router.get("/categories", response_model=ApiResponse)
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.name))
    cats = result.scalars().all()
    return ApiResponse(data=[
        {"id": c.id, "name": c.name, "parent_id": c.parent_id}
        for c in cats
    ])


@router.post("/categories", response_model=ApiResponse)
async def create_category(req: CategoryCreateRequest, db: AsyncSession = Depends(get_db)):
    if req.parent_id:
        parent = await db.scalar(select(Category).where(Category.id == req.parent_id))
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")
    cat = Category(name=req.name.strip(), parent_id=req.parent_id)
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return ApiResponse(data={"id": cat.id, "name": cat.name, "parent_id": cat.parent_id})


@router.delete("/categories/{category_id}", response_model=ApiResponse)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    cat = await db.scalar(select(Category).where(Category.id == category_id))
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    children_count = await db.scalar(
        select(func.count(Category.id)).where(Category.parent_id == category_id)
    )
    if children_count:
        raise HTTPException(status_code=409, detail=f"Нельзя удалить: есть {children_count} дочерних категорий")

    products_count = await db.scalar(
        select(func.count(Product.product_id)).where(Product.category_id == category_id)
    )
    if products_count:
        raise HTTPException(status_code=409, detail=f"Нельзя удалить: {products_count} товаров в этой категории")

    await db.delete(cat)
    await db.commit()
    return ApiResponse(data={"deleted": category_id})


# --------------------------------------------------------------------------
# UOM + Package types
# --------------------------------------------------------------------------

@router.get("/uom", response_model=ApiResponse)
async def list_uom(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UOM).order_by(UOM.code))
    return ApiResponse(data=[
        {"id": u.id, "code": u.code, "name_ru": u.name_ru, "base_unit": u.base_unit}
        for u in result.scalars().all()
    ])


@router.get("/packages", response_model=ApiResponse)
async def list_packages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PackageType).order_by(PackageType.code))
    return ApiResponse(data=[
        {"id": p.id, "code": p.code, "name_ru": p.name_ru}
        for p in result.scalars().all()
    ])
