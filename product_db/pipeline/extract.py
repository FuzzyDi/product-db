"""Step 4: извлечение атрибутов (бренд, тип товара, объём, упаковка, вариант)."""
import re
import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import Brand, BrandAlias, ProductType
from product_db.nlp.fuzzy import find_best_brand
from product_db.nlp.lemmatize import lemmatize_ru
from .context import PipelineContext

# --------------------------------------------------------------------------
# Quantity regex
# --------------------------------------------------------------------------
_QTY_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(мл|мл\.|ml|л\b|литр|litre|l\b|г\b|г\.|гр\b|gram|g\b|кг|kg|шт|pcs|pc\b)",
    re.IGNORECASE,
)
_UNIT_MAP = {
    "мл": "ml", "мл.": "ml", "ml": "ml",
    "л": "l", "л.": "l", "литр": "l", "litre": "l", "l": "l",
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

# --------------------------------------------------------------------------
# In-memory alias cache: list[(alias, brand_id, canonical_name)]
# Обновляется раз в 5 минут
# --------------------------------------------------------------------------
_alias_cache: list[tuple[str, int, str]] = []
_alias_cache_ts: float = 0.0
_CACHE_TTL = 300  # секунд


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


async def _get_alias_cache(session: AsyncSession) -> list[tuple[str, int, str]]:
    global _alias_cache, _alias_cache_ts
    if time.time() - _alias_cache_ts < _CACHE_TTL and _alias_cache:
        return _alias_cache
    result = await session.execute(
        select(BrandAlias.alias, BrandAlias.brand_id, Brand.name_canonical)
        .join(Brand, Brand.id == BrandAlias.brand_id)
    )
    _alias_cache = [(row.alias, row.brand_id, row.name_canonical) for row in result.all()]
    _alias_cache_ts = time.time()
    return _alias_cache


async def _find_product_type(session: AsyncSession, tokens: list[str]) -> tuple[int | None, str | None]:
    result = await session.execute(
        select(ProductType.id, ProductType.name_ru, ProductType.keywords_ru)
    )
    rows = result.all()
    lemmas = set(lemmatize_ru(" ".join(tokens)).split())

    best_id, best_name, best_score = None, None, 0
    for row in rows:
        if not row.keywords_ru:
            continue
        kw_lemmas = {lemmatize_ru(kw) for kw in row.keywords_ru}
        matches = len(lemmas & kw_lemmas)
        if matches > best_score:
            best_score = matches
            best_id = row.id
            best_name = row.name_ru

    return best_id, best_name


async def run(ctx: PipelineContext, session: AsyncSession) -> PipelineContext:
    text = ctx.name_raw

    # Количество и упаковка — через regex
    ctx.quantity_value, ctx.quantity_unit = _extract_quantity(text)
    ctx.package_code = _extract_package(text)

    # Бренд — точное слово + fuzzy fallback
    aliases = await _get_alias_cache(session)
    brand_id, brand_name, score = find_best_brand(text, aliases)
    if brand_id:
        ctx.brand_id = brand_id
        ctx.brand_name = brand_name
        ctx.field_sources["brand_id"] = f"extract:{ctx.source_id}:{score:.0f}"

    # Тип товара — по лемматизированным ключевым словам
    ctx.product_type_id, ctx.product_type_name = await _find_product_type(session, ctx.tokens)
    if ctx.product_type_id:
        ctx.field_sources["product_type_id"] = f"extract:{ctx.source_id}"

    return ctx
