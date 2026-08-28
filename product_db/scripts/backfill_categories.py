"""Обновление category_id у существующих товаров по текущему product_type."""
import asyncio

from sqlalchemy import select

from product_db.db.session import AsyncSessionLocal
from product_db.models.db import Category, Product, ProductType
from product_db.pipeline.route import _PRODUCT_TYPE_TO_CATEGORY


async def main():
    async with AsyncSessionLocal() as session:
        category_by_name = {
            row.name: row.id
            for row in (
                await session.execute(select(Category.id, Category.name))
            ).all()
        }
        type_by_id = {
            row.id: row.name_ru
            for row in (
                await session.execute(select(ProductType.id, ProductType.name_ru))
            ).all()
        }

        updated = 0
        skipped_certified = 0
        skipped_missing_mapping = 0

        products = (
            await session.execute(
                select(Product).where(Product.product_type_id.is_not(None))
            )
        ).scalars().all()

        for product in products:
            type_name = type_by_id.get(product.product_type_id)
            category_name = _PRODUCT_TYPE_TO_CATEGORY.get(type_name)
            if not category_name:
                skipped_missing_mapping += 1
                continue

            expected_category_id = category_by_name.get(category_name)
            if not expected_category_id or product.category_id == expected_category_id:
                continue

            if product.status == "certified":
                skipped_certified += 1
                continue

            product.category_id = expected_category_id
            updated += 1

        await session.commit()
        print(
            f"Категории товаров: обновлено {updated}, "
            f"пропущено certified {skipped_certified}, "
            f"без маппинга {skipped_missing_mapping}."
        )


if __name__ == "__main__":
    asyncio.run(main())
