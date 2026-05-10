"""Обучение системы на основе решений операторов.

Что учимся:
- correct_field(brand_id/brand_name) → добавляем вариант написания в brand_aliases
- confirm_product → если бренд был определён корректно, подтверждаем паттерн
- correct_field(product_type_id) → собираем частоту токенов (не меняем автоматически)
"""
import logging
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import BrandAlias, OperatorDecision, Product, ProductType

logger = logging.getLogger(__name__)


async def learn_from_decision(
    session: AsyncSession,
    decision: OperatorDecision,
    product: Product,
) -> int:
    """Обрабатывает решение оператора. Возвращает количество созданных записей."""
    learned = 0

    if decision.decision_type in ("correct_field", "confirm_mxik"):
        field = decision.field_name
        if field in ("brand_id", "brand_name"):
            learned += await _learn_brand_alias(session, decision, product)

    elif decision.decision_type == "confirm_product":
        # Бренд был корректно определён пайплайном — ищем незарегистрированные варианты
        if product.brand_id and product.name_raw:
            learned += await _extract_brand_variants(session, product)

    if learned:
        logger.info(
            "learner: decision=%s type=%s product=%s → +%d записей",
            decision.id, decision.decision_type, product.product_id, learned,
        )
        # Сбрасываем кэш алиасов в extract.py
        _invalidate_alias_cache()

    return learned


async def _learn_brand_alias(
    session: AsyncSession,
    decision: OperatorDecision,
    product: Product,
) -> int:
    """Оператор исправил бренд → сохраняем старое написание как alias."""
    new_brand_id = (decision.new_value or {}).get("brand_id")
    if not new_brand_id:
        return 0

    candidates = set()

    # 1. Старое название бренда (что пайплайн думал)
    old_brand_name = (decision.old_value or {}).get("brand_name")
    if old_brand_name and old_brand_name.strip():
        candidates.add(old_brand_name.strip())

    # 2. Если пайплайн ничего не нашёл, ищем в сыром имени слова вокруг
    #    нового canonical — эвристика (1-2 слова)
    if not candidates and product.name_raw:
        result = await session.execute(
            select(BrandAlias.alias).where(BrandAlias.brand_id == new_brand_id)
        )
        known = {r.alias.lower() for r in result.all()}
        tokens = product.name_raw.split()
        for i, token in enumerate(tokens):
            if token.upper() in known or token.lower() in known:
                # Соседний токен тоже может быть частью бренда
                if i > 0:
                    candidates.add(tokens[i - 1])
                candidates.add(token)

    learned = 0
    for alias in candidates:
        learned += await _add_alias_if_new(session, new_brand_id, alias)

    return learned


async def _extract_brand_variants(
    session: AsyncSession,
    product: Product,
) -> int:
    """Из подтверждённого товара извлекаем варианты написания бренда."""
    if not product.brand_id or not product.name_raw:
        return 0

    result = await session.execute(
        select(BrandAlias.alias).where(BrandAlias.brand_id == product.brand_id)
    )
    known_lower = {r.alias.lower() for r in result.all()}

    # Ищем в сыром имени токены, похожие на уже известные aliases
    tokens = product.name_raw.split()
    learned = 0

    # 1- и 2-граммы
    candidates = []
    for i in range(len(tokens)):
        candidates.append(tokens[i])
        if i + 1 < len(tokens):
            candidates.append(f"{tokens[i]} {tokens[i+1]}")

    for cand in candidates:
        if cand.lower() in known_lower:
            continue  # уже есть
        # Добавляем только если в known есть похожий (UPPERCASE версия)
        if cand.upper() in {a.upper() for a in known_lower}:
            learned += await _add_alias_if_new(session, product.brand_id, cand)

    return learned


async def _add_alias_if_new(
    session: AsyncSession,
    brand_id: int,
    alias: str,
) -> int:
    if not alias or len(alias) < 2:
        return 0
    existing = await session.scalar(
        select(BrandAlias).where(
            BrandAlias.brand_id == brand_id,
            BrandAlias.alias == alias,
        )
    )
    if existing:
        return 0
    session.add(BrandAlias(brand_id=brand_id, alias=alias, source="operator"))
    return 1


def _invalidate_alias_cache() -> None:
    """Сбрасывает кэш алиасов в pipeline/extract.py."""
    try:
        from product_db.pipeline import extract
        extract._alias_cache_ts = 0.0
    except Exception:
        pass
