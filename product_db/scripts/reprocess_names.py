"""Перегенерация name_canonical/pos/receipt для всех продуктов.

Использует уже извлечённые данные (brand, product_type, qty) и обновлённую
логику generate.build_canonical. Новые raw_input_log записи не создаются.

Запуск внутри контейнера:
  python -m product_db.scripts.reprocess_names
"""
import asyncio

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from product_db.config import settings
from product_db.models.db import Product, ProductType
from product_db.pipeline.generate import build_canonical


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # Загружаем все типы товаров
        pt_result = await session.execute(select(ProductType.id, ProductType.name_ru))
        type_map = {row.id: row.name_ru for row in pt_result.all()}

        # Загружаем все продукты
        result = await session.execute(select(Product))
        products = result.scalars().all()

        updated = 0
        for p in products:
            product_type_name = type_map.get(p.product_type_id) if p.product_type_id else None
            new_canonical = build_canonical(
                product_type=product_type_name,
                brand=p.brand_name,
                subbrand=None,
                variant=None,
                quantity_value=p.quantity_value,
                quantity_unit=p.quantity_unit,
                package_code=p.package_code,
                name_raw=p.name_raw,
            )
            if new_canonical != p.name_canonical:
                await session.execute(
                    update(Product)
                    .where(Product.product_id == p.product_id)
                    .values(
                        name_canonical=new_canonical,
                        name_pos=new_canonical[:20],
                        name_receipt=new_canonical[:40],
                    )
                )
                updated += 1

        await session.commit()
        print(f"Обновлено: {updated} из {len(products)} товаров")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
