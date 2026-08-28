"""Step 6: поиск ИКПУ (MXIK)."""
import re
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import MxikCatalog, ProductTypeMxikMap
from .context import PipelineContext
from .barcode import GLOBAL_TYPES

_TSQUERY_WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+")


async def _find_by_barcode(session: AsyncSession, barcode: str) -> MxikCatalog | None:
    result = await session.execute(
        select(MxikCatalog)
        .where(MxikCatalog.international_code == barcode, MxikCatalog.is_active.is_(True))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _find_group_by_text(session: AsyncSession, name: str) -> MxikCatalog | None:
    """Поиск группового ИКПУ через full-text search. Только is_group_code=true."""
    words = [w.lower() for w in _TSQUERY_WORD_RE.findall(name) if len(w) > 2]
    if not words:
        return None
    query_str = " | ".join(words[:5])
    result = await session.execute(
        text(
            """
            SELECT id FROM mxik_catalog
            WHERE search_vector @@ to_tsquery('russian', :q)
              AND is_active = true
              AND is_group_code = true
            ORDER BY ts_rank(search_vector, to_tsquery('russian', :q)) DESC
            LIMIT 1
            """
        ),
        {"q": query_str},
    )
    row = result.first()
    if not row:
        return None
    result2 = await session.execute(select(MxikCatalog).where(MxikCatalog.id == row.id))
    return result2.scalar_one_or_none()


async def _find_group_code(session: AsyncSession, product_type_id: int) -> tuple[str | None, Decimal]:
    result = await session.execute(
        select(ProductTypeMxikMap.mxik_group_code, ProductTypeMxikMap.confidence)
        .where(ProductTypeMxikMap.product_type_id == product_type_id)
        .order_by(ProductTypeMxikMap.confidence.desc())
        .limit(1)
    )
    row = result.first()
    if row:
        return row.mxik_group_code, row.confidence
    return None, Decimal("0")


async def run(ctx: PipelineContext, session: AsyncSession) -> PipelineContext:
    mxik: MxikCatalog | None = None
    confidence = Decimal("0")

    # 1. По штрихкоду (высокая уверенность)
    if ctx.barcode and ctx.barcode_type in GLOBAL_TYPES:
        mxik = await _find_by_barcode(session, ctx.barcode)
        if mxik:
            confidence = Decimal("0.95")

    # 2. По названию/классификации — только групповые коды (средняя уверенность)
    if mxik is None and ctx.name_normalized:
        mxik = await _find_group_by_text(session, ctx.name_normalized)
        if mxik:
            confidence = Decimal("0.50")

    # 3. Групповой код из маппинга product_type → mxik (низкая уверенность)
    if mxik is None and ctx.product_type_id:
        group_code, group_conf = await _find_group_code(session, ctx.product_type_id)
        if group_code:
            ctx.mxik_code = group_code
            ctx.mxik_is_group_code = True
            ctx.mxik_confidence = group_conf
            ctx.issues.append("MXIK_GROUP_CODE")
            return ctx

    if mxik:
        ctx.mxik_code = mxik.mxik
        ctx.mxik_is_group_code = mxik.is_group_code
        ctx.mxik_confidence = confidence
        ctx.field_sources["mxik_code"] = f"mxik_step:{ctx.source_id}"

    return ctx
