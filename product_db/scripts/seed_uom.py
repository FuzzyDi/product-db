"""Заполнение таблицы единиц измерения с русскими и узбекскими названиями."""
import asyncio
from sqlalchemy import select
from product_db.db.session import AsyncSessionLocal
from product_db.models.db import UOM

# code → (name_ru, name_uz_latn, name_uz_cyrl, base_unit, factor)
UOM_DATA = [
    # Штучные
    ("pcs",  "шт",   "dona",         "дона",         None,  None),
    ("pair", "пара", "juft",         "жуфт",         None,  None),
    ("set",  "набор","to'plam",      "тўплам",       None,  None),
    ("pack", "уп",   "qadoq",        "қадоқ",        None,  None),
    ("box",  "кор",  "quti",         "қути",         None,  None),
    ("roll", "рул",  "rulon",        "рулон",        None,  None),
    # Масса
    ("g",    "г",    "g",            "г",            "kg",  "0.001"),
    ("kg",   "кг",   "kg",           "кг",           None,  None),
    ("mg",   "мг",   "mg",           "мг",           "g",   "0.001"),
    ("t",    "т",    "tonna",        "тонна",        "kg",  "1000"),
    # Объём жидкости
    ("ml",   "мл",   "ml",           "мл",           "l",   "0.001"),
    ("l",    "л",    "l",            "л",            None,  None),
    ("cl",   "сл",   "cl",           "сл",           "l",   "0.01"),
    # Прочие объёмы
    ("m",    "м",    "m",            "м",            None,  None),
    ("cm",   "см",   "sm",           "см",           "m",   "0.01"),
    ("mm",   "мм",   "mm",           "мм",           "m",   "0.001"),
    ("m2",   "м²",   "m2",           "м²",           None,  None),
    ("m3",   "м³",   "m3",           "м³",           None,  None),
]


async def main():
    async with AsyncSessionLocal() as db:
        for code, name_ru, name_uz_latn, name_uz_cyrl, base_unit, factor in UOM_DATA:
            existing = await db.scalar(select(UOM).where(UOM.code == code))
            if existing:
                existing.name_ru = name_ru
                existing.name_uz_latn = name_uz_latn
                existing.name_uz_cyrl = name_uz_cyrl
            else:
                db.add(UOM(
                    code=code,
                    name_ru=name_ru,
                    name_uz_latn=name_uz_latn,
                    name_uz_cyrl=name_uz_cyrl,
                    base_unit=base_unit,
                    factor=factor,
                ))
        await db.commit()
        print(f"Готово: {len(UOM_DATA)} единиц измерения.")


if __name__ == "__main__":
    asyncio.run(main())
