"""GET/POST /api/v1/refs — справочники."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import Brand, BrandAlias, Category, PackageType, ProductType, UOM
from product_db.models.schemas import ApiResponse

router = APIRouter(prefix="/refs", tags=["refs"])


# --------------------------------------------------------------------------
# Brands
# --------------------------------------------------------------------------

class BrandCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    manufacturer_id: int | None = None


class BrandAliasRequest(BaseModel):
    alias: str = Field(..., min_length=1, max_length=255)


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
    return ApiResponse(data=[
        {"id": b.id, "name_canonical": b.name_canonical, "manufacturer_id": b.manufacturer_id}
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


@router.post("/brands/{brand_id}/aliases", response_model=ApiResponse)
async def add_alias(brand_id: int, req: BrandAliasRequest, db: AsyncSession = Depends(get_db)):
    brand = await db.scalar(select(Brand).where(Brand.id == brand_id))
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    alias = BrandAlias(brand_id=brand_id, alias=req.alias.strip(), source="operator")
    db.add(alias)
    await db.commit()
    return ApiResponse(data={"brand_id": brand_id, "alias": alias.alias})


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

@router.get("/categories", response_model=ApiResponse)
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.name))
    cats = result.scalars().all()
    return ApiResponse(data=[
        {"id": c.id, "name": c.name, "parent_id": c.parent_id}
        for c in cats
    ])


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
