"""Оркестратор пайплайна (9 шагов)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import RawInputLog
from . import barcode, extract, generate, match, mxik_step, normalize, quality, route
from .context import PipelineContext


async def process(
    session: AsyncSession,
    *,
    source_id: str,
    source_type: str,
    payload: dict,
) -> PipelineContext:
    name_raw = payload.get("name", "").strip()
    bc = payload.get("barcode")
    if bc:
        bc = str(bc).strip()

    # Шаг 1: сохраняем raw_input_log иммутабельно
    log = RawInputLog(
        source_id=source_id,
        source_type=source_type,
        payload=payload,
        status="pending",
    )
    session.add(log)
    await session.flush()  # получаем id

    ctx = PipelineContext(
        raw_input_id=log.id,
        source_id=source_id,
        source_type=source_type,
        name_raw=name_raw,
        barcode=bc,
        extra={k: v for k, v in payload.items() if k not in ("name", "barcode")},
    )

    # Шаг 2: тип штрихкода
    ctx = barcode.run(ctx)

    # Шаг 3: нормализация
    ctx = normalize.run(ctx)

    # Шаг 4: извлечение атрибутов
    ctx = await extract.run(ctx, session)

    # Шаг 5: поиск / создание кандидата
    ctx = await match.run(ctx, session)

    # Шаг 6: MXIK
    ctx = await mxik_step.run(ctx, session)

    # Шаг 7: генерация названий
    ctx = generate.run(ctx)

    # Шаг 8: качество
    ctx = quality.run(ctx)

    # Шаг 9: маршрутизация + запись в products
    ctx = await route.run(ctx, session)

    # Обновляем raw_input_log
    log.product_id = ctx.product_id
    log.status = "processed"
    log.processed_at = datetime.now(timezone.utc)

    await session.commit()
    return ctx
