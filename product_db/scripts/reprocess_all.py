"""Полный перезапуск пайплайна для всех продуктов в БД.

Заново определяет: бренд, тип товара, количество, canonical name, issues.
Не создаёт новые raw_input_log записи — обновляет существующие продукты.

Запуск:
  docker exec product-db-backend-1 python -m product_db.scripts.reprocess_all
"""
import asyncio
import re
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from product_db.config import settings
from product_db.models.db import Brand, BrandAlias, Category, OperatorDecision, Product, ProductType
from product_db.nlp.fuzzy import find_best_brand
from product_db.nlp.lemmatize import lemmatize_ru
from product_db.pipeline.generate import build_canonical
from product_db.pipeline.extract import _QTY_RE, _UNIT_MAP, _PKG_RE, _PKG_MAP, _apply_product_type_overrides
from product_db.pipeline.mxik_step import _find_group_by_text, _find_group_code
from product_db.pipeline.quality import CRITICAL_ISSUES, _CONFIDENCE_PENALTIES, _COMPLETENESS_PENALTIES
from product_db.pipeline.route import (
    AUTO_CONFIRM_THRESHOLD,
    _PRODUCT_TYPE_TO_CATEGORY,
    _build_review_reasons,
    _is_structurally_complete_for_auto_verify,
)

# Issues которые пайплайн ставит при отсутствии данных
_ISSUE_MISSING_BRAND        = "MISSING_BRAND"
_ISSUE_MISSING_TYPE         = "MISSING_PRODUCT_TYPE"
_ISSUE_MISSING_MXIK         = "MISSING_MXIK"


def _extract_quantity(text: str):
    m = _QTY_RE.search(text)
    if not m:
        return None, None
    val = Decimal(m.group(1).replace(",", "."))
    unit = _UNIT_MAP.get(m.group(2).lower().rstrip("."))
    return val, unit


def _extract_package(text: str):
    m = _PKG_RE.search(text)
    if not m:
        return None
    return _PKG_MAP.get(m.group(1).lower())


def _find_product_type(tokens: list[str], types: list[tuple[int, str, list[str]]]) -> tuple[int | None, str | None]:
    lemmas = set(lemmatize_ru(" ".join(tokens)).split())
    best_id, best_name, best_score = None, None, 0
    for pt_id, pt_name, keywords in types:
        if not keywords:
            continue
        kw_lemmas = {lemmatize_ru(kw) for kw in keywords}
        matches = len(lemmas & kw_lemmas)
        if matches > best_score:
            best_score = matches
            best_id = pt_id
            best_name = pt_name
    return best_id, best_name


def _recalc_issues(issues: list[str], brand_id, product_type_id, mxik_code, mxik_is_group_code) -> list[str]:
    result = list(issues or [])
    if brand_id or True:  # пересчитываем с нуля
        result = [i for i in result if i != _ISSUE_MISSING_BRAND]
        result = [i for i in result if i != _ISSUE_MISSING_TYPE]
    result = [i for i in result if i not in (_ISSUE_MISSING_MXIK, "MXIK_GROUP_CODE")]
    if not brand_id:
        if _ISSUE_MISSING_BRAND not in result:
            result.append(_ISSUE_MISSING_BRAND)
    if not product_type_id:
        if _ISSUE_MISSING_TYPE not in result:
            result.append(_ISSUE_MISSING_TYPE)
    if not mxik_code:
        if _ISSUE_MISSING_MXIK not in result:
            result.append(_ISSUE_MISSING_MXIK)
    elif mxik_is_group_code and "MXIK_GROUP_CODE" not in result:
        result.append("MXIK_GROUP_CODE")
    return result


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,;/\-–—]+", text.lower()) if t]


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # Загружаем алиасы брендов
        alias_result = await session.execute(
            select(BrandAlias.alias, BrandAlias.brand_id, Brand.name_canonical)
            .join(Brand, Brand.id == BrandAlias.brand_id)
        )
        aliases = [(row.alias, row.brand_id, row.name_canonical) for row in alias_result.all()]
        print(f"Алиасов брендов: {len(aliases)}")

        # Загружаем типы товаров
        pt_result = await session.execute(
            select(ProductType.id, ProductType.name_ru, ProductType.name_uz_latn, ProductType.keywords_ru)
        )
        pt_rows = pt_result.all()
        types = [(row.id, row.name_ru, row.keywords_ru or []) for row in pt_rows]
        type_map = {row.id: row.name_ru for row in pt_rows}
        type_uz_map = {row.id: row.name_uz_latn for row in pt_rows}
        print(f"Типов товаров: {len(types)}")

        # Загружаем категории — строим маппинг name → id
        cat_result = await session.execute(select(Category.id, Category.name))
        cat_by_name = {row.name: row.id for row in cat_result.all()}
        print(f"Категорий: {len(cat_by_name)}")

        # Поля, которые оператор исправлял вручную, не трогаем
        decision_rows = await session.execute(
            select(
                OperatorDecision.product_id,
                OperatorDecision.field_name,
            ).where(
                OperatorDecision.decision_type == "correct_field",
                OperatorDecision.field_name.is_not(None),
            )
        )
        protected_by_product: dict = {}
        for product_id, field_name in decision_rows.all():
            if not field_name:
                continue
            fields = protected_by_product.setdefault(product_id, set())
            fields.add(field_name)
            if field_name in {"brand_id", "brand_name"}:
                fields.update({"brand_id", "brand_name"})

        # Загружаем все продукты
        products_result = await session.execute(select(Product))
        products = products_result.scalars().all()
        print(f"Товаров для обработки: {len(products)}")

        updated = 0
        for p in products:
            if not p.name_raw:
                continue

            name_raw = p.name_raw.strip()
            tokens = _tokenize(name_raw)

            protected_fields = protected_by_product.get(p.product_id, set())

            # Бренд — пересчитываем всегда, кроме реально поправленных оператором
            if {"brand_id", "brand_name"} & protected_fields:
                brand_id, brand_name = p.brand_id, p.brand_name
            else:
                brand_id, brand_name, _ = find_best_brand(name_raw, aliases)

            # Тип товара — пересчитываем всегда, кроме реально поправленных оператором
            if "product_type_id" in protected_fields:
                product_type_id = p.product_type_id
                product_type_name = type_map.get(p.product_type_id)
            else:
                product_type_id, product_type_name = _find_product_type(tokens, types)

            package_code = _extract_package(name_raw) or p.package_code

            # Количество и упаковка
            qty_value, qty_unit = _extract_quantity(name_raw)
            eff_qty_value = qty_value or p.quantity_value
            eff_qty_unit = qty_unit or p.quantity_unit
            eff_package = package_code or p.package_code

            override_type_id, override_type_name = await _apply_product_type_overrides(
                SimpleNamespace(
                    brand_name=brand_name,
                    package_code=package_code,
                    tokens=tokens,
                    quantity_value=eff_qty_value,
                    quantity_unit=eff_qty_unit,
                ),
                session,
            )
            if override_type_id and "product_type_id" not in protected_fields:
                product_type_id = override_type_id
                product_type_name = override_type_name

            product_type_uz = type_uz_map.get(product_type_id) if product_type_id else None

            # Canonical name (рус.)
            new_canonical = build_canonical(
                product_type=product_type_name,
                brand=brand_name,
                subbrand=None,
                variant=None,
                quantity_value=eff_qty_value,
                quantity_unit=eff_qty_unit,
                package_code=eff_package,
                name_raw=name_raw,
                lang="ru",
            )

            # Canonical name (уз. лат.)
            new_uz_latn = build_canonical(
                product_type=product_type_uz or product_type_name,
                brand=brand_name,
                subbrand=None,
                variant=None,
                quantity_value=eff_qty_value,
                quantity_unit=eff_qty_unit,
                package_code=eff_package,
                name_raw=name_raw,
                lang="uz",
            ) if (brand_name or product_type_uz or product_type_name) else None

            # Категория — пересчитываем по актуальному маппингу, кроме реально поправленных оператором
            if "category_id" in protected_fields:
                new_category_id = p.category_id
            else:
                new_category_id = None
                if product_type_name:
                    category_name = _PRODUCT_TYPE_TO_CATEGORY.get(product_type_name)
                    if category_name:
                        new_category_id = cat_by_name.get(category_name)

            # ИКПУ — если раньше не был найден, пробуем переиспользовать live-логику:
            # 1) групповой поиск по тексту; 2) маппинг product_type -> group MXIK.
            mxik_code = p.mxik_code
            mxik_is_group_code = bool(p.mxik_is_group_code)
            mxik_confidence = p.mxik_confidence
            if not mxik_code:
                group_mxik = None
                if p.name_normalized:
                    group_mxik = await _find_group_by_text(session, p.name_normalized)
                if group_mxik:
                    mxik_code = group_mxik.mxik
                    mxik_is_group_code = bool(group_mxik.is_group_code)
                    mxik_confidence = Decimal("0.50")
                elif product_type_id:
                    group_code, group_conf = await _find_group_code(session, product_type_id)
                    if group_code:
                        mxik_code = group_code
                        mxik_is_group_code = True
                        mxik_confidence = group_conf

            # Issues — сохраняем MXIK-related, пересчитываем brand/type
            new_issues = _recalc_issues(
                p.issues,
                brand_id,
                product_type_id,
                mxik_code,
                mxik_is_group_code,
            )

            # Обновляем только если что-то изменилось
            changes = {}
            if brand_id != p.brand_id or brand_name != p.brand_name:
                changes["brand_id"] = brand_id
                changes["brand_name"] = brand_name
            if product_type_id != p.product_type_id:
                changes["product_type_id"] = product_type_id
            if qty_value and qty_value != p.quantity_value:
                changes["quantity_value"] = qty_value
            if qty_unit and qty_unit != p.quantity_unit:
                changes["quantity_unit"] = qty_unit
            if new_canonical != p.name_canonical:
                changes["name_canonical"] = new_canonical
                changes["name_pos"] = new_canonical[:20]
                changes["name_receipt"] = new_canonical[:40]
            if new_uz_latn and new_uz_latn != p.name_uz_latn:
                changes["name_uz_latn"] = new_uz_latn
            if new_category_id != p.category_id:
                changes["category_id"] = new_category_id
            if mxik_code != p.mxik_code:
                changes["mxik_code"] = mxik_code
            if mxik_is_group_code != bool(p.mxik_is_group_code):
                changes["mxik_is_group_code"] = mxik_is_group_code
            if mxik_confidence != p.mxik_confidence:
                changes["mxik_confidence"] = mxik_confidence
            if new_issues != (p.issues or []):
                changes["issues"] = new_issues

            # Пересчитываем scores на основе актуальных issues
            confidence = 1.0
            completeness = 1.0
            for issue in new_issues:
                confidence -= _CONFIDENCE_PENALTIES.get(issue, 0)
                completeness -= _COMPLETENESS_PENALTIES.get(issue, 0)
            new_confidence = round(max(0.0, confidence), 3)
            new_completeness = round(max(0.0, completeness), 3)
            if new_confidence != float(p.confidence_score or 0):
                changes["confidence_score"] = new_confidence
                changes["completeness_score"] = new_completeness

            has_critical = any(issue in CRITICAL_ISSUES for issue in new_issues)
            auto = (
                (
                    new_confidence >= AUTO_CONFIRM_THRESHOLD
                    or _is_structurally_complete_for_auto_verify(
                        brand_id=brand_id,
                        product_type_id=product_type_id,
                        category_id=new_category_id,
                        mxik_code=mxik_code,
                        mxik_is_group_code=mxik_is_group_code,
                        issues=new_issues,
                    )
                )
                and not has_critical
                and not mxik_is_group_code
            )
            new_review_required = not auto
            if p.status == "certified":
                new_status = p.status
                new_review_required = False
            else:
                new_status = "verified" if auto else "draft"
            new_review_reasons = _build_review_reasons(
                review_required=new_review_required,
                issues=new_issues,
                mxik_is_group_code=mxik_is_group_code,
            )

            if new_review_required != p.review_required:
                changes["review_required"] = new_review_required
            if new_status != p.status:
                changes["status"] = new_status
            if new_review_reasons != (p.review_reasons or []):
                changes["review_reasons"] = new_review_reasons

            if changes:
                await session.execute(
                    update(Product)
                    .where(Product.product_id == p.product_id)
                    .values(**changes)
                )
                updated += 1

        await session.commit()
        print(f"\nГотово. Обновлено: {updated} из {len(products)} товаров.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
