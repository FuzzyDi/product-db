"""GET /api/v1/stats — статистика."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import MxikCatalog, MxikSyncLog, Product, ProductBarcode
from product_db.models.schemas import ApiResponse, MxikHealthResponse, PipelineStatsResponse

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/pipeline", response_model=ApiResponse)
async def pipeline_stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(Product.product_id))) or 0

    result = await db.execute(
        select(Product.status, func.count(Product.product_id))
        .group_by(Product.status)
    )
    by_status = {row[0]: row[1] for row in result.all()}

    review_queue = await db.scalar(
        select(func.count(Product.product_id)).where(Product.review_required.is_(True))
    ) or 0
    with_brand = await db.scalar(
        select(func.count(Product.product_id)).where(Product.brand_id.isnot(None))
    ) or 0
    with_mxik = await db.scalar(
        select(func.count(Product.product_id)).where(Product.mxik_code.isnot(None))
    ) or 0
    with_barcode = await db.scalar(
        select(func.count(ProductBarcode.id.distinct()))
    ) or 0

    data = PipelineStatsResponse(
        total_products=total,
        by_status=by_status,
        review_queue_size=review_queue,
        with_brand=with_brand,
        with_mxik=with_mxik,
        with_barcode=with_barcode,
    )
    return ApiResponse(data=data.model_dump())


@router.get("/mxik-health", response_model=ApiResponse)
async def mxik_health(db: AsyncSession = Depends(get_db)):
    log = await db.scalar(
        select(MxikSyncLog).order_by(MxikSyncLog.started_at.desc()).limit(1)
    )
    total = await db.scalar(select(func.count(MxikCatalog.id))) or 0
    active = await db.scalar(
        select(func.count(MxikCatalog.id)).where(MxikCatalog.is_active.is_(True))
    ) or 0

    data = MxikHealthResponse(
        last_sync_status=log.status if log else None,
        last_sync_at=log.finished_at.isoformat() if log and log.finished_at else None,
        total_records=total,
        active_records=active,
    )
    return ApiResponse(data=data.model_dump())
