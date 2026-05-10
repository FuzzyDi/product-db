"""Celery задача: пакетное обучение из решений операторов (hourly catch-all)."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from product_db.db.session import AsyncSessionLocal
from product_db.models.db import OperatorDecision, Product
from product_db.pipeline.learner import learn_from_decision
from .celery_app import app

logger = logging.getLogger(__name__)

_LEARN_TYPES = ("correct_field", "confirm_product", "confirm_mxik")


@app.task
def batch_learn():
    asyncio.run(_run())


async def _run():
    since = datetime.now(timezone.utc) - timedelta(hours=2)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OperatorDecision)
            .where(
                OperatorDecision.created_at >= since,
                OperatorDecision.decision_type.in_(_LEARN_TYPES),
            )
        )
        decisions = result.scalars().all()

        total = 0
        for dec in decisions:
            product = await session.get(Product, dec.product_id)
            if not product:
                continue
            total += await learn_from_decision(session, dec, product)

        await session.commit()
        logger.info("batch_learn: решений=%d, создано записей=%d", len(decisions), total)
