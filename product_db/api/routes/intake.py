"""POST /api/v1/intake — приём товаров."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.core.ratelimit import limiter

from product_db.db.session import get_db
from product_db.models.db import RawInputLog
from product_db.models.schemas import (
    ApiResponse,
    BatchIntakeRequest,
    IntakeResponse,
    IntakeStatusResponse,
    ProductIntakeRequest,
)
from product_db.pipeline.processor import process
from product_db.tasks.process_input import process_input

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("/single", response_model=ApiResponse)
@limiter.limit("120/minute")
async def intake_single(request: Request, req: ProductIntakeRequest, db: AsyncSession = Depends(get_db)):
    payload = {"name": req.name, "barcode": req.barcode, **req.extra}
    ctx = await process(db, source_id=req.source_id, source_type="api", payload=payload)
    data = IntakeResponse(
        raw_input_id=ctx.raw_input_id,
        product_id=ctx.product_id,
        is_new=ctx.is_new,
        confidence_score=ctx.confidence_score,
        review_required=ctx.review_required,
        issues=ctx.issues,
        status="verified" if not ctx.review_required else "draft",
    )
    return ApiResponse(data=data.model_dump())


@router.post("/batch", response_model=ApiResponse)
@limiter.limit("20/minute")
async def intake_batch(request: Request, req: BatchIntakeRequest):
    """Ставит товары в очередь Celery (асинхронно)."""
    task_ids = []
    for item in req.items:
        payload = {"name": item.name, "barcode": item.barcode, **item.extra}
        task = process_input.delay(
            source_id=item.source_id,
            source_type=req.source_type,
            payload=payload,
        )
        task_ids.append(task.id)
    return ApiResponse(data={"task_ids": task_ids, "count": len(task_ids)})


@router.get("/{raw_input_id}/status", response_model=ApiResponse)
async def intake_status(raw_input_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RawInputLog).where(RawInputLog.id == raw_input_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Not found")
    data = IntakeStatusResponse(
        raw_input_id=log.id,
        product_id=log.product_id,
        status=log.status,
        error=log.error,
    )
    return ApiResponse(data=data.model_dump())
