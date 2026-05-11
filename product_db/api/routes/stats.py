"""GET /api/v1/stats — статистика."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import (
    BrandAlias, MxikCatalog, MxikSyncLog, OperatorDecision, Product, ProductBarcode, QualityStat,
)
from product_db.models.schemas import ApiResponse, MxikHealthResponse, PipelineStatsResponse
from product_db.tasks.celery_app import app as celery_app

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
    with_category = await db.scalar(
        select(func.count(Product.product_id)).where(Product.category_id.isnot(None))
    ) or 0
    with_type = await db.scalar(
        select(func.count(Product.product_id)).where(Product.product_type_id.isnot(None))
    ) or 0

    from sqlalchemy import cast, Date
    from datetime import date
    certified_today = await db.scalar(
        select(func.count(Product.product_id)).where(
            Product.status == "certified",
            cast(Product.updated_at, Date) == date.today(),
        )
    ) or 0

    data = PipelineStatsResponse(
        total_products=total,
        by_status=by_status,
        review_queue_size=review_queue,
        with_brand=with_brand,
        with_mxik=with_mxik,
        with_barcode=with_barcode,
        with_category=with_category,
        with_type=with_type,
        certified_today=certified_today,
    )
    return ApiResponse(data=data.model_dump())


@router.get("/mxik-health", response_model=ApiResponse)
async def mxik_health(db: AsyncSession = Depends(get_db)):
    log = await db.scalar(
        select(MxikSyncLog).order_by(MxikSyncLog.started_at.desc()).limit(1)
    )
    # Приближённый счётчик из pg_class — мгновенно, не сканирует 429K строк
    total = await db.scalar(
        text("SELECT reltuples::bigint FROM pg_class WHERE relname = 'mxik_catalog'")
    ) or 0
    # Активные берём из последней успешной синхронизации
    active = (log.records_total or total) if (log and log.status == "success") else total

    data = MxikHealthResponse(
        last_sync_status=log.status if log else None,
        last_sync_at=log.finished_at.isoformat() if log and log.finished_at else None,
        total_records=total,
        active_records=active,
    )
    return ApiResponse(data=data.model_dump())


@router.get("/quality", response_model=ApiResponse)
async def quality_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """История метрик качества + текущее состояние обучения."""
    # История из quality_stats
    result = await db.execute(
        select(QualityStat)
        .order_by(QualityStat.period_date.desc())
        .limit(days)
    )
    history = [
        {
            "period_date": s.period_date.isoformat(),
            "total_products": s.total_products,
            "with_brand": s.with_brand,
            "with_mxik": s.with_mxik,
            "auto_confirmed": s.auto_confirmed,
            "review_queue_size": s.review_queue_size,
            "avg_confidence": float(s.avg_confidence) if s.avg_confidence else None,
        }
        for s in result.scalars().all()
    ]

    # Статистика решений по типам
    dec_result = await db.execute(
        select(OperatorDecision.decision_type, func.count(OperatorDecision.id))
        .group_by(OperatorDecision.decision_type)
    )
    decisions_by_type = {row[0]: row[1] for row in dec_result.all()}

    # Количество выученных aliases (от operator)
    learned_aliases = await db.scalar(
        select(func.count(BrandAlias.id)).where(BrandAlias.source == "operator")
    ) or 0

    # Сертифицировано по дням (из operator_decisions)
    certified_history_result = await db.execute(
        text(
            """
            SELECT DATE(created_at AT TIME ZONE 'UTC') AS day, COUNT(*) AS cnt
            FROM operator_decisions
            WHERE decision_type = 'confirm_product'
              AND created_at >= NOW() - (:days * INTERVAL '1 day')
            GROUP BY day
            ORDER BY day
            """
        ),
        {"days": days},
    )
    certified_history = [
        {"date": str(row.day), "count": row.cnt}
        for row in certified_history_result.all()
    ]

    return ApiResponse(data={
        "history": history,
        "decisions_by_type": decisions_by_type,
        "learned_aliases": learned_aliases,
        "certified_history": certified_history,
    })


@router.get("/celery", response_model=ApiResponse)
async def celery_health():
    """Статус очереди Celery: ожидающие, активные, воркеры."""
    import asyncio

    # Кол-во задач в очереди Redis (неблокирующий запрос)
    try:
        from redis.asyncio import from_url as redis_from_url
        from product_db.config import settings
        redis = await redis_from_url(settings.redis_url)
        pending = await redis.llen("celery")
        await redis.aclose()
    except Exception:
        pending = None

    # Активные и зарезервированные задачи через Celery inspect (с таймаутом)
    active = 0
    reserved = 0
    workers: list[str] = []
    try:
        loop = asyncio.get_event_loop()
        inspect = celery_app.control.inspect(timeout=1.5)

        def _inspect():
            a = inspect.active() or {}
            r = inspect.reserved() or {}
            return a, r

        active_map, reserved_map = await loop.run_in_executor(None, _inspect)
        workers = list(active_map.keys())
        active = sum(len(v) for v in active_map.values())
        reserved = sum(len(v) for v in reserved_map.values())
    except Exception:
        pass

    return ApiResponse(data={
        "pending": pending,
        "active": active,
        "reserved": reserved,
        "workers": workers,
        "worker_count": len(workers),
    })
