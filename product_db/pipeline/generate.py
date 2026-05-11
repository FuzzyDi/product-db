"""Step 7: генерация канонических названий.

Формула: [Тип товара] [БРЕНД] [Суббренд] [Вариант] [Объём] [Упаковка]
Пример:  Вода питьевая NESTLE Pure Life негазированная 0.5л ПЭТ
"""
from .context import PipelineContext

_UNIT_RU = {
    "ml": "мл", "l": "л", "g": "г", "kg": "кг",
    "pcs": "шт", "pack": "уп", "mg": "мг",
    "pair": "пара", "set": "набор", "box": "кор", "roll": "рул",
}
_UNIT_UZ = {
    "ml": "ml", "l": "l", "g": "g", "kg": "kg",
    "pcs": "dona", "pack": "qadoq", "mg": "mg",
    "pair": "juft", "set": "to'plam", "box": "quti", "roll": "rulon",
}


def _format_quantity(value, unit: str | None, lang: str = "ru") -> str | None:
    if value is None or unit is None:
        return None
    v = float(value)
    v_str = str(int(v)) if v == int(v) else f"{v:g}"
    unit_map = _UNIT_UZ if lang == "uz" else _UNIT_RU
    unit_display = unit_map.get(unit, unit)
    return f"{v_str}{unit_display}"


def build_canonical(
    product_type: str | None,
    brand: str | None,
    subbrand: str | None,
    variant: str | None,
    quantity_value=None,
    quantity_unit: str | None = None,
    package_code: str | None = None,
    name_raw: str | None = None,
    lang: str = "ru",
) -> str:
    parts = []
    if product_type:
        parts.append(product_type)
    if brand:
        parts.append(brand.upper())
    if subbrand:
        parts.append(subbrand)
    if variant:
        parts.append(variant)
    qty = _format_quantity(quantity_value, quantity_unit, lang=lang)
    if qty:
        parts.append(qty)
    if package_code:
        parts.append(package_code)

    if parts and (brand or product_type):
        return " ".join(parts)
    return name_raw or ""


def run(ctx: PipelineContext) -> PipelineContext:
    canonical = build_canonical(
        product_type=ctx.product_type_name,
        brand=ctx.brand_name,
        subbrand=None,
        variant=ctx.variant,
        quantity_value=ctx.quantity_value,
        quantity_unit=ctx.quantity_unit,
        package_code=ctx.package_code,
        name_raw=ctx.name_raw,
        lang="ru",
    )
    ctx.name_canonical = canonical
    ctx.name_pos = canonical[:20]
    ctx.name_receipt = canonical[:40]
    ctx.name_catalog = canonical
    return ctx
