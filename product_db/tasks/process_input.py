"""Celery задача: обработка одного входящего товара."""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from product_db.config import settings
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
    # Создаём свежий engine для каждой задачи — избегаем конфликтов event loop
    engine = create_async_engine(settings.database_url, pool_size=1, max_overflow=0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            return await process(session, source_id=source_id, source_type=source_type, payload=payload)
    finally:
        await engine.dispose()
