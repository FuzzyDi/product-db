"""Step 9: маршрутизация — авто-подтверждение или очередь ревью."""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from product_db.models.db import Category, OperatorDecision, Product
from .context import PipelineContext
from .quality import CRITICAL_ISSUES

AUTO_CONFIRM_THRESHOLD = 0.85

# Опасные поля пайплайн не перезаписывает автоматически, если они уже заполнены
_ALWAYS_PROTECTED_FIELDS = {"mxik_code", "mxik_package_code", "mxik_is_group_code"}
# Статусы выше которых пайплайн не опускает
_PROTECTED_STATUSES = {"certified"}

_PRODUCT_TYPE_TO_CATEGORY = {
    "Вода питьевая": "Вода негазированная",
    "Напиток газированный": "Газированные напитки",
    "Напиток негазированный": "Холодный чай и готовые напитки",
    "Сок фруктовый": "Соки, нектары и морсы",
    "Нектар фруктовый": "Соки, нектары и морсы",
    "Сок томатный": "Соки, нектары и морсы",
    "Энергетический напиток": "Энергетики и спортивные напитки",
    "Чай чёрный": "Чай",
    "Чай зелёный": "Чай",
    "Чай травяной": "Чай",
    "Холодный чай": "Холодный чай и готовые напитки",
    "Готовый завтрак": "Сухие завтраки и каши",
    "Кофе растворимый": "Кофе и какао",
    "Кофе молотый": "Кофе и какао",
    "Кофе в зёрнах": "Кофе и какао",
    "Какао": "Кофе и какао",
    "Цикорий": "Кофе и какао",
    "Взбитые сливки": "Молоко и сливки",
    "Молоко": "Молоко и сливки",
    "Кефир": "Кефир, йогурт, ряженка",
    "Йогурт": "Кефир, йогурт, ряженка",
    "Сырок глазированный": "Молочные продукты и яйца",
    "Сметана": "Молочные продукты и яйца",
    "Творог": "Молочные продукты и яйца",
    "Масло сливочное": "Масло сливочное",
    "Сыр твёрдый": "Сыры",
    "Сыр плавленый": "Сыры",
    "Мороженое": "Мороженое",
    "Масло подсолнечное": "Растительные масла",
    "Масло оливковое": "Растительные масла",
    "Маргарин": "Маргарин и спреды",
    "Крупа рисовая": "Рис",
    "Крупа гречневая": "Крупы",
    "Крупа манная": "Крупы",
    "Овсяные хлопья": "Сухие завтраки и каши",
    "Мука пшеничная": "Мука и смеси",
    "Макаронные изделия": "Макароны и лапша",
    "Сахар": "Сахар",
    "Соль": "Соль",
    "Специи и приправы": "Специи и приправы",
    "Перец молотый": "Специи и приправы",
    "Шоколад плиточный": "Шоколад и конфеты",
    "Шоколадные конфеты": "Шоколад и конфеты",
    "Карамель": "Жевательная резинка и леденцы",
    "Драже": "Жевательная резинка и леденцы",
    "Хлебцы": "Хлеб и выпечка",
    "Сахарозаменитель": "Сахар",
    "Мармелад": "Жевательная резинка и леденцы",
    "Жевательная резинка": "Жевательная резинка и леденцы",
    "Печенье": "Печенье и вафли",
    "Крекер": "Печенье и вафли",
    "Вафли": "Печенье и вафли",
    "Маршмеллоу": "Жевательная резинка и леденцы",
    "Торт": "Торты и пирожные",
    "Кекс": "Хлеб и выпечка",
    "Пирог": "Хлеб и выпечка",
    "Подарочный набор конфет": "Шоколад и конфеты",
    "Подарочный набор косметики": "Хозяйственные товары",
    "Хлеб": "Хлеб и выпечка",
    "Хлебобулочные изделия": "Хлеб и выпечка",
    "Декор для выпечки": "Хлеб и выпечка",
    "Салат готовый": "Салаты и закуски",
    "Картофельные полуфабрикаты": "Замороженные полуфабрикаты",
    "Чипсы": "Чипсы и сухарики",
    "Снеки и сухарики": "Чипсы и сухарики",
    "Орехи": "Орехи и семечки",
    "Попкорн": "Попкорн",
    "Кетчуп": "Кетчупы и томатные соусы",
    "Майонез": "Майонез",
    "Соус томатный": "Кетчупы и томатные соусы",
    "Уксус": "Соевый соус и маринады",
    "Свежие овощи": "Свежие овощи",
    "Горчица": "Горчица и хрен",
    "Варенье и джем": "Фруктовые консервы и варенье",
    "Мёд": "Фруктовые консервы и варенье",
    "Консервы рыбные": "Рыбные консервы",
    "Консервы мясные": "Консервы и соленья",
    "Консервы овощные": "Овощные консервы",
    "Грибы консервированные": "Овощные консервы",
    "Икра красная": "Рыбные консервы",
    "Сгущённое молоко": "Молоко и сливки",
    "Колбаса варёная": "Колбасы варёные",
    "Колбаса сырокопчёная": "Колбасы копчёные",
    "Сосиски и сардельки": "Сосиски и сардельки",
    "Рыба": "Рыба свежая и охлаждённая",
    "Стиральный порошок": "Стиральные порошки",
    "Жидкость для стирки": "Гели и капсулы для стирки",
    "Кондиционер для белья": "Кондиционеры для белья",
    "Пятновыводитель и отбеливатель": "Пятновыводители и отбеливатели",
    "Средство для посуды": "Жидкость для мытья посуды",
    "Чистящее средство": "Универсальные чистящие средства",
    "Бритвенный станок и кассеты": "Средства для бритья",
    "Шампунь": "Шампуни",
    "Гель для душа": "Гели для душа",
    "Мыло туалетное": "Мыло",
    "Зубная щётка": "Зубные щётки",
    "Зубная паста": "Зубные пасты",
    "Дезодорант": "Дезодоранты и антиперспиранты",
    "Шампунь и кондиционер": "Кондиционеры и маски",
    "Крем для рук": "Кремы и лосьоны для тела",
    "Крем для лица": "Кремы для лица",
    "Маска для лица": "Маски для лица",
    "Влажные салфетки": "Влажные салфетки",
    "Женские гигиенические прокладки": "Женская гигиена",
    "Бумажные салфетки": "Бумажные салфетки",
    "Бумажные полотенца": "Бумажные полотенца",
    "Ватные диски": "Ватные диски и тампоны",
    "Носки": "Хозяйственные товары",
    "Щётка для одежды": "Хозяйственные товары",
    "Мочалка и банная губка": "Хозяйственные товары",
    "Стаканы": "Посуда",
    "Электрочайник": "Хозяйственные товары",
    "Подгузники": "Подгузники и пелёнки",
    "Детское питание": "Детское питание",
    "Корм для кошек": "Корм для кошек",
    "Корм для собак": "Корм для собак",
}


def _is_structurally_complete_for_auto_verify(
    *,
    brand_id,
    product_type_id,
    category_id,
    mxik_code,
    mxik_is_group_code,
    issues: list[str] | None,
) -> bool:
    issues = issues or []
    has_critical = any(issue in CRITICAL_ISSUES for issue in issues)
    return bool(
        brand_id
        and product_type_id
        and category_id
        and mxik_code
        and not mxik_is_group_code
        and not has_critical
    )


def _build_review_reasons(
    *,
    review_required: bool,
    issues: list[str] | None,
    mxik_is_group_code: bool,
) -> list[str]:
    issues = issues or []
    if not review_required:
        return []
    critical = [issue for issue in issues if issue in CRITICAL_ISSUES]
    if critical:
        return critical
    if mxik_is_group_code:
        return ["GROUP_MXIK"]
    for issue in (
        "MISSING_MXIK",
        "MISSING_PRODUCT_TYPE",
        "MISSING_BRAND",
        "MISSING_QUANTITY",
        "FUZZY_MATCH",
    ):
        if issue in issues:
            return [issue]
    return ["LOW_CONFIDENCE"]


async def _resolve_category_id(
    session: AsyncSession,
    product_type_name: str | None,
) -> int | None:
    if not product_type_name:
        return None
    category_name = _PRODUCT_TYPE_TO_CATEGORY.get(product_type_name)
    if not category_name:
        return None
    return await session.scalar(
        select(Category.id).where(Category.name == category_name).limit(1)
    )


async def _operator_override_fields(
    session: AsyncSession,
    product_id,
) -> set[str]:
    rows = await session.execute(
        select(OperatorDecision.field_name).where(
            OperatorDecision.product_id == product_id,
            OperatorDecision.decision_type == "correct_field",
            OperatorDecision.field_name.is_not(None),
        )
    )
    fields = {row[0] for row in rows.all() if row[0]}
    if "brand_id" in fields or "brand_name" in fields:
        fields.update({"brand_id", "brand_name"})
    return fields


async def run(ctx: PipelineContext, session: AsyncSession) -> PipelineContext:
    has_critical = any(i in CRITICAL_ISSUES for i in ctx.issues)
    resolved_category_id = await _resolve_category_id(session, ctx.product_type_name)
    auto = (
        (
            ctx.confidence_score >= AUTO_CONFIRM_THRESHOLD
            or _is_structurally_complete_for_auto_verify(
                brand_id=ctx.brand_id,
                product_type_id=ctx.product_type_id,
                category_id=resolved_category_id,
                mxik_code=ctx.mxik_code,
                mxik_is_group_code=ctx.mxik_is_group_code,
                issues=ctx.issues,
            )
        )
        and not has_critical
        and not ctx.mxik_is_group_code
    )

    if auto:
        new_status = "verified"
        review_required = False
    else:
        new_status = "draft"
        review_required = True
    ctx.review_reasons = _build_review_reasons(
        review_required=review_required,
        issues=ctx.issues,
        mxik_is_group_code=ctx.mxik_is_group_code,
    )

    ctx.review_required = review_required

    values: dict = {
        "name_normalized": ctx.name_normalized,
        "name_canonical": ctx.name_canonical,
        "name_pos": ctx.name_pos,
        "name_receipt": ctx.name_receipt,
        "name_catalog": ctx.name_catalog,
        "brand_id": ctx.brand_id,
        "brand_name": ctx.brand_name,
        "product_type_id": ctx.product_type_id,
        "category_id": resolved_category_id,
        "quantity_value": ctx.quantity_value,
        "quantity_unit": ctx.quantity_unit,
        "package_code": ctx.package_code,
        "mxik_code": ctx.mxik_code,
        "mxik_package_code": ctx.mxik_package_code,
        "mxik_is_group_code": ctx.mxik_is_group_code,
        "mxik_confidence": ctx.mxik_confidence,
        "confidence_score": ctx.confidence_score,
        "completeness_score": ctx.completeness_score,
        "issues": ctx.issues,
        "review_required": review_required,
        "review_reasons": ctx.review_reasons,
        "field_sources": ctx.field_sources,
        "status": new_status,
    }

    if not ctx.is_new:
        # Существующий товар: защищаем оператор-установленные поля
        result = await session.execute(
            select(Product).where(Product.product_id == ctx.product_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            # Не опускаем certified/verified ниже
            if existing.status in _PROTECTED_STATUSES:
                values["status"] = existing.status
                values["review_required"] = False
                ctx.review_required = False

            # Опасные поля не перезаписываем автоматически
            for field in _ALWAYS_PROTECTED_FIELDS:
                if getattr(existing, field, None) is not None:
                    values.pop(field, None)

            # Brand / type / category защищаем только если было реальное решение оператора
            protected_fields = await _operator_override_fields(session, ctx.product_id)
            for field in ("brand_id", "brand_name", "product_type_id", "category_id"):
                if field in protected_fields and getattr(existing, field, None) is not None:
                    values.pop(field, None)

    await session.execute(
        update(Product)
        .where(Product.product_id == ctx.product_id)
        .values(**values)
    )
    return ctx
