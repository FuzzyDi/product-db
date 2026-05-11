"""POST /api/v1/admin — административные действия."""
import asyncio
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

from product_db.models.schemas import ApiResponse

router = APIRouter(prefix="/admin", tags=["admin"])

# Состояние текущего reprocess (в памяти процесса)
_reprocess_state: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


async def _run_reprocess():
    from product_db.scripts.reprocess_all import main as reprocess_main
    _reprocess_state["running"] = True
    _reprocess_state["started_at"] = datetime.utcnow().isoformat()
    _reprocess_state["finished_at"] = None
    _reprocess_state["result"] = None
    _reprocess_state["error"] = None
    try:
        await reprocess_main()
        _reprocess_state["result"] = "ok"
    except Exception as e:
        _reprocess_state["error"] = str(e)
    finally:
        _reprocess_state["running"] = False
        _reprocess_state["finished_at"] = datetime.utcnow().isoformat()


@router.post("/reprocess", response_model=ApiResponse)
async def start_reprocess(background_tasks: BackgroundTasks):
    """Запуск полного перераспознавания всех товаров."""
    if _reprocess_state["running"]:
        return ApiResponse(success=False, error="Уже запущено")
    background_tasks.add_task(_run_reprocess)
    return ApiResponse(data={"started": True})


@router.get("/reprocess", response_model=ApiResponse)
async def reprocess_status():
    """Статус последнего запуска перераспознавания."""
    return ApiResponse(data=dict(_reprocess_state))
