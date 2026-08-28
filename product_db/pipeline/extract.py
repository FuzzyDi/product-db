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
    r"(мл|мл\.|ml|л\b|литр|litre|l\b|г\b|г\.|гр\b|gr\b|gram|g\b|кг|kg|шт|pcs|pc\b|sht\b)",
    re.IGNORECASE,
)
_UNIT_MAP = {
    "мл": "ml", "мл.": "ml", "ml": "ml",
    "л": "l", "л.": "l", "литр": "l", "litre": "l", "l": "l",
    "г": "g", "г.": "g", "гр": "g", "gr": "g", "gram": "g", "g": "g",
    "кг": "kg", "kg": "kg",
    "шт": "pcs", "pcs": "pcs", "pc": "pcs", "sht": "pcs",
}

# --------------------------------------------------------------------------
# Package regex
# --------------------------------------------------------------------------
_PKG_RE = re.compile(
    r"(?:\b|^)(пэт|пет|pet|стекло|glass|стекл|пакет|bag|tetra|тетра|банка|can|коробка|box|картон|ж/?б)(?:\b|$)",
    re.IGNORECASE,
)
_PKG_MAP = {
    "пэт": "PET", "пет": "PET", "pet": "PET",
    "стекло": "GLASS", "стекл": "GLASS", "glass": "GLASS",
    "пакет": "BAG", "bag": "BAG",
    "tetra": "TETRA", "тетра": "TETRA",
    "банка": "CAN", "can": "CAN",
    "ж/б": "CAN", "жб": "CAN",
    "коробка": "BOX", "box": "BOX", "картон": "BOX",
}

# --------------------------------------------------------------------------
# In-memory alias cache: list[(alias, brand_id, canonical_name)]
# Обновляется раз в 5 минут
# --------------------------------------------------------------------------
_alias_cache: list[tuple[str, int, str]] = []
_alias_cache_ts: float = 0.0
_CACHE_TTL = 300  # секунд
_READY_TO_DRINK_TEA_BRANDS = {"LIPTON"}
_SOFT_DRINK_BRANDS = {"FANTOLA", "COCA-COLA", "TROPIC"}
_JUICE_BRANDS = {"J7"}
_ENERGY_DRINK_BRANDS = {"BIG BEAR"}
_COCKTAIL_DRINK_BRANDS = {"УХХ"}
_CANDY_BRANDS = {"FRUIT-TELLA", "MELLER", "CHUPA CHUPS", "SKITTLES"}
_HOUSEHOLD_CLEANER_BRANDS = {"SANFOR", "SANITA", "ЧИСТИН"}
_SHAMPOO_BRANDS = {"TRESEMME", "CLEAR", "ЧИСТАЯ ЛИНИЯ"}
_FACE_CARE_BRANDS = {"ЧИСТАЯ ЛИНИЯ", "SKIN SHINE", "ЧЕРНЫЙ ЖЕМЧУГ"}
_SPICE_BRANDS = {"ПРИПРАВЫЧ"}
_GIFT_COSMETIC_BRANDS = {"LURE", "ARKO"}
_READY_SALAD_BRANDS = {"ОТ ОЛЕГА"}
_CHOCOLATE_CANDY_BRANDS = {"FERRERO ROCHER", "AFTER EIGHT", "ANTON BERG", "BAILEYS"}
_CRISPBREAD_BRANDS = {"FINN CRISP", "DR. KARG"}


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


async def _get_product_type_by_name(session: AsyncSession, name_ru: str) -> tuple[int | None, str | None]:
    result = await session.execute(
        select(ProductType.id, ProductType.name_ru).where(ProductType.name_ru == name_ru).limit(1)
    )
    row = result.first()
    if not row:
        return None, None
    return row.id, row.name_ru


async def _apply_product_type_overrides(
    ctx: PipelineContext,
    session: AsyncSession,
) -> tuple[int | None, str | None]:
    tokens = set(ctx.tokens)

    if (
        ctx.brand_name in _READY_TO_DRINK_TEA_BRANDS
        and ctx.package_code == "CAN"
        and ("напиток" in tokens or "чай" in tokens)
    ):
        return await _get_product_type_by_name(session, "Холодный чай")

    if ctx.brand_name in _SOFT_DRINK_BRANDS and "напиток" in tokens:
        return await _get_product_type_by_name(session, "Напиток газированный")

    if ctx.brand_name in _SOFT_DRINK_BRANDS:
        return await _get_product_type_by_name(session, "Напиток газированный")

    if ctx.brand_name in _JUICE_BRANDS:
        return await _get_product_type_by_name(session, "Сок фруктовый")

    if ctx.brand_name in _ENERGY_DRINK_BRANDS or "enery" in tokens:
        return await _get_product_type_by_name(session, "Энергетический напиток")

    if ctx.brand_name in _COCKTAIL_DRINK_BRANDS and "коктейль" in tokens:
        return await _get_product_type_by_name(session, "Напиток негазированный")

    if "гречка" in tokens or "гречневая" in tokens:
        return await _get_product_type_by_name(session, "Крупа гречневая")

    if "манная" in tokens or "манка" in tokens:
        return await _get_product_type_by_name(session, "Крупа манная")

    if "рис" in tokens or "рисовая" in tokens:
        return await _get_product_type_by_name(session, "Крупа рисовая")

    if ctx.brand_name in _CANDY_BRANDS:
        if "мармелад" in tokens:
            return await _get_product_type_by_name(session, "Мармелад")
        if "маршмелоу" in tokens or "marshmallow" in tokens:
            return await _get_product_type_by_name(session, "Маршмеллоу")
        if "gum" in tokens or "жевательная" in tokens or "bubble" in tokens:
            return await _get_product_type_by_name(session, "Жевательная резинка")
        return await _get_product_type_by_name(session, "Карамель")

    if ctx.brand_name in _CHOCOLATE_CANDY_BRANDS:
        return await _get_product_type_by_name(session, "Шоколадные конфеты")

    if ctx.brand_name == "DUPLO":
        return await _get_product_type_by_name(session, "Шоколад плиточный")

    if ctx.brand_name == "RITTER SPORT":
        return await _get_product_type_by_name(session, "Шоколад плиточный")

    if ctx.brand_name == "PRINGLES":
        return await _get_product_type_by_name(session, "Чипсы")

    if ctx.brand_name == "LEIBNIZ":
        return await _get_product_type_by_name(session, "Печенье")

    if ctx.brand_name == "RAFFAELLO":
        return await _get_product_type_by_name(session, "Шоколадные конфеты")

    if ctx.brand_name in _CRISPBREAD_BRANDS or "хлебцы" in tokens:
        return await _get_product_type_by_name(session, "Хлебцы")

    if ctx.brand_name in _HOUSEHOLD_CLEANER_BRANDS:
        if "посуды" in tokens:
            return await _get_product_type_by_name(session, "Средство для посуды")
        if "белизна" in tokens or "отбеливатель" in tokens:
            return await _get_product_type_by_name(session, "Пятновыводитель и отбеливатель")
        if "белья" in tokens and ("кондиционер" in tokens or "ополаскиватель" in tokens):
            return await _get_product_type_by_name(session, "Кондиционер для белья")
        if {"антижир", "antijir", "жироудалитель", "антиналёт", "антиналет", "стёкол", "стекол", "труб", "плит", "техники"} & tokens:
            return await _get_product_type_by_name(session, "Чистящее средство")

    if ctx.brand_name in _SHAMPOO_BRANDS and "шампунь" in tokens:
        return await _get_product_type_by_name(session, "Шампунь")

    if ctx.brand_name in _SPICE_BRANDS or "приправа" in tokens:
        return await _get_product_type_by_name(session, "Специи и приправы")

    if ctx.brand_name in _READY_SALAD_BRANDS and ({"оливье", "винегрет", "фунчоза", "морковча", "свекла", "капуста"} & tokens):
        return await _get_product_type_by_name(session, "Салат готовый")

    if "посыпка" in tokens:
        return await _get_product_type_by_name(session, "Декор для выпечки")

    if "драже" in tokens:
        return await _get_product_type_by_name(session, "Драже")

    if ctx.brand_name == "GILLETTE" and ({"станок", "бритва", "кассеты"} & tokens):
        return await _get_product_type_by_name(session, "Бритвенный станок и кассеты")

    if ctx.brand_name == "PASABAHCE" and ({"стакан", "стаканы"} & tokens):
        return await _get_product_type_by_name(session, "Стаканы")

    if ctx.brand_name == "STARLUX" and ("электрочайник" in tokens or "чайник" in tokens):
        return await _get_product_type_by_name(session, "Электрочайник")

    if (ctx.brand_name in _GIFT_COSMETIC_BRANDS or ctx.brand_name == "Я САМАЯ") and ("набор" in tokens or "подарочный" in tokens):
        return await _get_product_type_by_name(session, "Подарочный набор косметики")

    if ctx.brand_name == "DOVE":
        if ("body" in tokens and "wash" in tokens) or ("гель" in tokens and "душа" in tokens):
            return await _get_product_type_by_name(session, "Гель для душа")
        if "крем" in tokens and "рук" in tokens:
            return await _get_product_type_by_name(session, "Крем для рук")
        if "шампунь" in tokens:
            return await _get_product_type_by_name(session, "Шампунь")

    if ctx.brand_name == "ALPENGURT" and ("сливки" in tokens or "взбитые" in tokens):
        return await _get_product_type_by_name(session, "Взбитые сливки")

    if ctx.brand_name == "DR. OETKER" and ("мюсли" in tokens or "vitalis" in tokens):
        return await _get_product_type_by_name(session, "Готовый завтрак")

    if ctx.brand_name == "BORCHERS" and ({"эритрит", "эритритол", "сукралоза", "подсластитель"} & tokens):
        return await _get_product_type_by_name(session, "Сахарозаменитель")

    if ctx.brand_name == "BARILLA":
        if {"спагетти", "спагеттони", "пенне", "ригате", "маккерони", "макароны", "фузилли", "фузиллони", "лингвини", "тальятелле", "тальятелле", "феттуччине", "джирандоле", "орешьетте", "тортильони", "linguine", "fusilli", "penne", "maccheroni", "spaghetti", "tagliatelle", "fettuccine", "tortiglioni"} & tokens:
            return await _get_product_type_by_name(session, "Макаронные изделия")

    if ctx.brand_name == "LAVAZZA" and ({"espresso", "crema", "caffe", "gusto"} & tokens):
        quantity_unit = getattr(ctx, "quantity_unit", None)
        quantity_value = getattr(ctx, "quantity_value", None)
        if quantity_unit == "kg" or (quantity_unit == "g" and quantity_value and quantity_value >= Decimal("500")):
            return await _get_product_type_by_name(session, "Кофе в зёрнах")
        return await _get_product_type_by_name(session, "Кофе молотый")

    if ctx.brand_name == "MOVENPICK" and ("брауни" in tokens or "brownie" in tokens):
        return await _get_product_type_by_name(session, "Кекс")

    if ctx.brand_name == "COPPENRATH" and "тарталетки" in tokens:
        return await _get_product_type_by_name(session, "Печенье")

    if ctx.brand_name == "CAPELLA" and ({"грибы", "шампиньоны"} & tokens):
        return await _get_product_type_by_name(session, "Грибы консервированные")

    if ctx.brand_name == "YORK" and "одежды" in tokens:
        return await _get_product_type_by_name(session, "Щётка для одежды")

    if (ctx.brand_name == "YORK" or ctx.brand_name == "ZUR") and ("губка" in tokens and "массажная" in tokens):
        return await _get_product_type_by_name(session, "Мочалка и банная губка")

    if ctx.brand_name == "MR. GROCC":
        if {"антилед", "антизасор", "очиститель", "ковров", "незамерзайка"} & tokens:
            return await _get_product_type_by_name(session, "Чистящее средство")
        return await _get_product_type_by_name(session, "Чистящее средство")

    if ctx.brand_name == "ВЫГОДНАЯ УБОРКА" and "антинакипин" in tokens:
        return await _get_product_type_by_name(session, "Чистящее средство")

    if "сгущенка" in tokens or "сгущёнка" in tokens or ("сгущенное" in tokens and "сахаром" in tokens):
        return await _get_product_type_by_name(session, "Сгущённое молоко")

    if ctx.brand_name in _FACE_CARE_BRANDS:
        if "маска" in tokens and "лица" in tokens:
            return await _get_product_type_by_name(session, "Маска для лица")
        if "крем" in tokens and "лица" in tokens:
            return await _get_product_type_by_name(session, "Крем для лица")

    if "wedges" in tokens or ("картофельные" in tokens and "дольки" in tokens):
        return await _get_product_type_by_name(session, "Картофельные полуфабрикаты")

    return None, None


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

    override_type_id, override_type_name = await _apply_product_type_overrides(ctx, session)
    if override_type_id:
        ctx.product_type_id = override_type_id
        ctx.product_type_name = override_type_name

    if ctx.product_type_id:
        ctx.field_sources["product_type_id"] = f"extract:{ctx.source_id}"

    return ctx
