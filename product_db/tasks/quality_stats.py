"""Celery задача: ежедневный сбор статистики качества."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from product_db.db.session import AsyncSessionLocal
from product_db.models.db import Product, QualityStat
from .celery_app import app

logger = logging.getLogger(__name__)


@app.task
def collect_quality_stats():
    asyncio.run(_collect())


async def _collect():
    async with AsyncSessionLocal() as session:
        total = await session.scalar(select(func.count(Product.product_id)))
        with_brand = await session.scalar(
            select(func.count(Product.product_id)).where(Product.brand_id.isnot(None))
        )
        with_mxik = await session.scalar(
            select(func.count(Product.product_id)).where(Product.mxik_code.isnot(None))
        )
        auto_confirmed = await session.scalar(
            select(func.count(Product.product_id)).where(Product.status == "verified")
        )
        review_queue = await session.scalar(
            select(func.count(Product.product_id)).where(Product.review_required.is_(True))
        )
        avg_conf = await session.scalar(select(func.avg(Product.confidence_score)))

        stat = QualityStat(
            period_date=datetime.now(timezone.utc),
            total_products=total,
            with_brand=with_brand,
            with_mxik=with_mxik,
            auto_confirmed=auto_confirmed,
            review_queue_size=review_queue,
            avg_confidence=round(float(avg_conf), 3) if avg_conf else None,
        )
        session.add(stat)
        await session.commit()
        logger.info("quality_stats: total=%d, with_brand=%d, with_mxik=%d", total, with_brand, with_mxik)
