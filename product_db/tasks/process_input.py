"""Celery задача: обработка одного входящего товара."""
import asyncio
import uuid

from product_db.db.session import AsyncSessionLocal
from product_db.pipeline.processor import process
from .celery_app import app


@app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_input(self, *, source_id: str, source_type: str, payload: dict) -> dict:
    try:
        ctx = asyncio.run(_run(source_id=source_id, source_type=source_type, payload=payload))
        return {
            "product_id": str(ctx.product_id),
            "raw_input_id": str(ctx.raw_input_id),
            "confidence_score": ctx.confidence_score,
            "review_required": ctx.review_required,
            "issues": ctx.issues,
        }
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run(*, source_id: str, source_type: str, payload: dict):
    async with AsyncSessionLocal() as session:
        return await process(session, source_id=source_id, source_type=source_type, payload=payload)
