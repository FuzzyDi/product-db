"""Step 7: генерация канонических названий.

Формула: [Тип товара] [БРЕНД] [Суббренд] [Вариант] [Объём] [Упаковка]
Пример:  Вода питьевая NESTLE Pure Life негазированная 0.5л ПЭТ
"""
from .context import PipelineContext


def _format_quantity(value, unit: str | None) -> str | None:
    if value is None or unit is None:
        return None
    v = float(value)
    # Целые числа без десятичной части
    if v == int(v):
        v_str = str(int(v))
    else:
        v_str = f"{v:g}"
    unit_display = {"ml": "мл", "l": "л", "g": "г", "kg": "кг", "pcs": "шт"}.get(unit, unit)
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
    qty = _format_quantity(quantity_value, quantity_unit)
    if qty:
        parts.append(qty)
    if package_code:
        parts.append(package_code)

    if parts:
        return " ".join(parts)
    # Фолбэк — сырое название
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
    )
    ctx.name_canonical = canonical
    ctx.name_pos = canonical[:20]
    ctx.name_receipt = canonical[:40]
    ctx.name_catalog = canonical
    return ctx
