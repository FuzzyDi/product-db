"""Step 4: извлечение атрибутов (бренд, тип товара, объём, упаковка, вариант)."""
import re
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import Brand, BrandAlias, ProductType
from .context import PipelineContext

# --------------------------------------------------------------------------
# Quantity regex: "0.5л" / "500 мл" / "1кг" / "200г" / "5шт"
# --------------------------------------------------------------------------
_QTY_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(мл|мл\.|ml|л\b|л\.|litre|литр|l\b|г\b|г\.|гр\b|gram|g\b|кг|kg|шт|pcs|pc\b)",
    re.IGNORECASE,
)
_UNIT_MAP = {
    "мл": "ml", "мл.": "ml", "ml": "ml",
    "л": "l", "л.": "l", "litre": "l", "литр": "l", "l": "l",
    "г": "g", "г.": "g", "гр": "g", "gram": "g", "g": "g",
    "кг": "kg", "kg": "kg",
    "шт": "pcs", "pcs": "pcs", "pc": "pcs",
}

# --------------------------------------------------------------------------
# Package regex
# --------------------------------------------------------------------------
_PKG_RE = re.compile(
    r"\b(пэт|пет|pet|стекло|glass|стекл|пакет|bag|tetra|тетра|банка|can|коробка|box|картон)\b",
    re.IGNORECASE,
)
_PKG_MAP = {
    "пэт": "PET", "пет": "PET", "pet": "PET",
    "стекло": "GLASS", "стекл": "GLASS", "glass": "GLASS",
    "пакет": "BAG", "bag": "BAG",
    "tetra": "TETRA", "тетра": "TETRA",
    "банка": "CAN", "can": "CAN",
    "коробка": "BOX", "box": "BOX", "картон": "BOX",
}


def _extract_quantity(text: str) -> tuple[Decimal | None, str | None]:
    m = _QTY_RE.search(text)
    if not m:
        return None, None
    val = Decimal(m.group(1).replace(",", "."))
    unit = _UNIT_MAP.get(m.group(2).lower().rstrip("."))
    return val, unit


def _extract_package(text: str) -> str | None:
    m = _PKG_RE.search(text)
    if not m:
        return None
    return _PKG_MAP.get(m.group(1).lower())


async def _find_brand(session: AsyncSession, text: str) -> tuple[int | None, str | None]:
    """Ищет бренд по тексту через brand_aliases (точное совпадение слова)."""
    # Загружаем все алиасы — для Этапа 1 (нет fuzzy)
    result = await session.execute(
        select(BrandAlias.brand_id, BrandAlias.alias, Brand.name_canonical)
        .join(Brand, Brand.id == BrandAlias.brand_id)
        .order_by(BrandAlias.alias)
    )
    rows = result.all()

    text_lower = text.lower()
    # Приоритет: более длинные алиасы первыми (чтобы "Coca-Cola" не перебивал "Cola")
    rows_sorted = sorted(rows, key=lambda r: len(r.alias), reverse=True)
    for row in rows_sorted:
        if re.search(r"\b" + re.escape(row.alias.lower()) + r"\b", text_lower):
            return row.brand_id, row.name_canonical
    return None, None


async def _find_product_type(session: AsyncSession, tokens: list[str]) -> tuple[int | None, str | None]:
    """Ищет тип товара по ключевым словам из product_types."""
    result = await session.execute(
        select(ProductType.id, ProductType.name_ru, ProductType.keywords_ru)
    )
    rows = result.all()

    token_set = set(tokens)
    best_id, best_name, best_score = None, None, 0
    for row in rows:
        if not row.keywords_ru:
            continue
        matches = sum(1 for kw in row.keywords_ru if kw.lower() in token_set)
        if matches > best_score:
            best_score = matches
            best_id = row.id
            best_name = row.name_ru
    return best_id, best_name


async def run(ctx: PipelineContext, session: AsyncSession) -> PipelineContext:
    text = ctx.name_raw

    ctx.quantity_value, ctx.quantity_unit = _extract_quantity(text)
    ctx.package_code = _extract_package(text)

    ctx.brand_id, ctx.brand_name = await _find_brand(session, text)
    if ctx.brand_id:
        ctx.field_sources["brand_id"] = f"extract:{ctx.source_id}"

    ctx.product_type_id, ctx.product_type_name = await _find_product_type(session, ctx.tokens)
    if ctx.product_type_id:
        ctx.field_sources["product_type_id"] = f"extract:{ctx.source_id}"

    return ctx
