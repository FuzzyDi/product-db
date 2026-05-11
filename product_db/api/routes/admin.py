"""POST /api/v1/admin — административные действия."""
import asyncio
from collections import Counter, defaultdict
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.db.session import get_db
from product_db.models.db import MxikCatalog, Product, ProductTypeMxikMap
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


@router.post("/build-mxik-map", response_model=ApiResponse)
async def build_mxik_map(db: AsyncSession = Depends(get_db)):
    """Строит product_type_mxik_map из certified товаров с ИКПУ."""
    # Certified товары с обоими полями
    result = await db.execute(
        select(Product.product_type_id, Product.mxik_code)
        .where(
            Product.status == "certified",
            Product.mxik_code.isnot(None),
            Product.product_type_id.isnot(None),
        )
    )
    rows = result.all()
    if not rows:
        return ApiResponse(data={"mapped": 0, "message": "Нет certified товаров с ИКПУ и типом"})

    # Получаем is_group_code для всех найденных ИКПУ
    mxik_codes = list({r.mxik_code for r in rows})
    cat_result = await db.execute(
        select(MxikCatalog.mxik, MxikCatalog.is_group_code)
        .where(MxikCatalog.mxik.in_(mxik_codes))
    )
    is_group: dict[str, bool] = {r.mxik: r.is_group_code for r in cat_result.all()}

    # Определяем группу для каждого товара
    type_counts: dict[int, Counter] = defaultdict(Counter)
    for product_type_id, mxik_code in rows:
        if is_group.get(mxik_code):
            group_code = mxik_code
        else:
            # Первые 8 цифр + 000000 → групповой код
            group_code = mxik_code[:8] + "000000"
        type_counts[product_type_id][group_code] += 1

    # Проверяем что эти группы реально существуют в каталоге
    all_group_codes = {gc for counts in type_counts.values() for gc in counts}
    valid_result = await db.execute(
        select(MxikCatalog.mxik)
        .where(MxikCatalog.mxik.in_(all_group_codes), MxikCatalog.is_group_code.is_(True))
    )
    valid_groups = {r.mxik for r in valid_result.all()}

    # Перезаписываем маппинг
    await db.execute(delete(ProductTypeMxikMap))

    mapped = 0
    for product_type_id, counts in type_counts.items():
        best_code = None
        best_cnt = 0
        for code, cnt in counts.most_common():
            if code in valid_groups:
                best_code, best_cnt = code, cnt
                break
        if best_code:
            total = sum(counts.values())
            db.add(ProductTypeMxikMap(
                product_type_id=product_type_id,
                mxik_group_code=best_code,
                confidence=round(best_cnt / total, 3),
            ))
            mapped += 1

    await db.commit()
    return ApiResponse(data={"mapped": mapped, "total_source_types": len(type_counts)})


@router.post("/apply-mxik-map", response_model=ApiResponse)
async def apply_mxik_map(db: AsyncSession = Depends(get_db)):
    """Назначает групповые ИКПУ товарам без ИКПУ на основе product_type_mxik_map."""
    map_result = await db.execute(select(ProductTypeMxikMap))
    mapping = {row.product_type_id: row.mxik_group_code for row in map_result.scalars().all()}

    if not mapping:
        return ApiResponse(data={"applied": 0, "message": "Карта пуста — сначала запустите 'Построить карту'"})

    # Фискальные поля из каталога
    group_codes = list(mapping.values())
    cat_result = await db.execute(
        select(MxikCatalog).where(MxikCatalog.mxik.in_(group_codes))
    )
    fiscal: dict[str, MxikCatalog] = {row.mxik: row for row in cat_result.scalars().all()}

    applied = 0
    for product_type_id, group_code in mapping.items():
        mxik_obj = fiscal.get(group_code)
        values: dict = {
            "mxik_code": group_code,
            "mxik_is_group_code": True,
            # issues: убираем MISSING_MXIK, добавляем MXIK_GROUP_CODE (без дубликатов)
            "issues": func.array_append(
                func.array_remove(
                    func.array_remove(Product.issues, "MISSING_MXIK"),
                    "MXIK_GROUP_CODE",
                ),
                "MXIK_GROUP_CODE",
            ),
        }
        if mxik_obj:
            values["label_required"] = mxik_obj.label
            values["label_for_check"] = mxik_obj.label_for_check
            values["cash_sale"] = mxik_obj.cash_sale

        result = await db.execute(
            update(Product)
            .where(
                Product.product_type_id == product_type_id,
                Product.mxik_code.is_(None),
            )
            .values(**values)
        )
        applied += result.rowcount

    await db.commit()
    return ApiResponse(data={"applied": applied})
