"""GET /api/v1/mxik — поиск ИКПУ."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import MxikCatalog, MxikPackage, MxikSyncLog
from product_db.models.schemas import ApiResponse

router = APIRouter(prefix="/mxik", tags=["mxik"])


@router.get("/search", response_model=ApiResponse)
async def search_mxik(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Поиск ИКПУ по тексту (full-text + trigram) или по штрихкоду."""
    # Если цифры — ищем по коду или штрихкоду
    if q.strip().isdigit():
        result = await db.execute(
            select(MxikCatalog)
            .where(
                (MxikCatalog.mxik.like(f"%{q}%")) |
                (MxikCatalog.international_code == q)
            )
            .where(MxikCatalog.is_active.is_(True))
            .limit(limit)
        )
        items = result.scalars().all()
    else:
        words = [w for w in q.split() if len(w) > 2]
        query_str = " | ".join(words[:6]) if words else q
        result = await db.execute(
            text(
                """
                SELECT * FROM mxik_catalog
                WHERE search_vector @@ to_tsquery('russian', :q)
                  AND is_active = true
                ORDER BY ts_rank(search_vector, to_tsquery('russian', :q)) DESC
                LIMIT :limit
                """
            ),
            {"q": query_str, "limit": limit},
        )
        rows = result.mappings().all()
        items = [dict(r) for r in rows]
        return ApiResponse(data={"items": items, "count": len(items)})

    data = [
        {
            "mxik": m.mxik,
            "name_ru": m.mxik_name_ru,
            "name_lat": m.mxik_name_lat,
            "international_code": m.international_code,
            "is_group_code": m.is_group_code,
            "label": m.label,
            "label_for_check": m.label_for_check,
            "cash_sale": m.cash_sale,
        }
        for m in items
    ]
    return ApiResponse(data={"items": data, "count": len(data)})


@router.get("/{mxik}/packages", response_model=ApiResponse)
async def mxik_packages(mxik: str, db: AsyncSession = Depends(get_db)):
    catalog = await db.scalar(
        select(MxikCatalog).where(MxikCatalog.mxik == mxik, MxikCatalog.is_active.is_(True))
    )
    if not catalog:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="MXIK not found")

    result = await db.execute(
        select(MxikPackage).where(MxikPackage.catalog_id == catalog.id)
    )
    packages = result.scalars().all()
    return ApiResponse(data={
        "mxik": mxik,
        "name_ru": catalog.mxik_name_ru,
        "packages": [
            {
                "code": p.code,
                "package_type": p.package_type,
                "name_ru": p.name_ru,
                "name_lat": p.name_lat,
            }
            for p in packages
        ],
    })


@router.get("/sync/status", response_model=ApiResponse)
async def sync_status(db: AsyncSession = Depends(get_db)):
    from product_db.models.db import MxikSyncLog
    from sqlalchemy import func
    log = await db.scalar(
        select(MxikSyncLog).order_by(MxikSyncLog.started_at.desc()).limit(1)
    )
    total = await db.scalar(
        select(func.count(MxikCatalog.id))
    ) or 0
    active = await db.scalar(
        select(func.count(MxikCatalog.id)).where(MxikCatalog.is_active.is_(True))
    ) or 0
    return ApiResponse(data={
        "last_sync": {
            "status": log.status if log else None,
            "started_at": log.started_at.isoformat() if log else None,
            "finished_at": log.finished_at.isoformat() if log and log.finished_at else None,
            "records_total": log.records_total if log else None,
            "records_added": log.records_added if log else None,
            "records_updated": log.records_updated if log else None,
        },
        "catalog": {"total": total, "active": active},
    })
