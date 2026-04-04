"""Seed script to populate the database with sample data for development."""
import asyncio
from app.database import engine, async_session, Base
from app.models import *  # noqa
from app.models.tax_shipping import TaxRate, ShippingMethod


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        location = Location(name="Main Store", address="123 Market Street")
        db.add(location)
        await db.flush()

        products_data = [
            ("Whole Milk", "whole-milk", "dairy", [
                ("1L", "MILK-1L", "8801234000001", 2.99),
                ("2L", "MILK-2L", "8801234000002", 4.99),
            ]),
            ("White Bread", "white-bread", "bakery", [
                ("Standard", "BREAD-STD", "8801234000010", 1.99),
            ]),
            ("Organic Eggs", "organic-eggs", "dairy", [
                ("6 pack", "EGG-6", "8801234000020", 3.49),
                ("12 pack", "EGG-12", "8801234000021", 5.99),
            ]),
            ("Coca-Cola", "coca-cola", "beverages", [
                ("330ml Can", "COKE-330", "8801234000030", 1.29),
                ("500ml Bottle", "COKE-500", "8801234000031", 1.79),
                ("2L Bottle", "COKE-2L", "8801234000032", 2.99),
            ]),
            ("Banana", "banana", "fruits", [
                ("Per kg", "BANANA-KG", "8801234000040", 1.49),
            ]),
        ]

        for title, handle, ptype, variants_data in products_data:
            product = Product(title=title, handle=handle, product_type=ptype, status="active", tags=[ptype])
            for vtitle, sku, barcode, price in variants_data:
                variant = ProductVariant(title=vtitle, sku=sku, barcode=barcode, price=price)
                inv_item = InventoryItem()
                inv_item.levels.append(InventoryLevel(location_id=location.id, available=100, low_stock_threshold=10))
                variant.inventory_item = inv_item
                product.variants.append(variant)
            image_name = title.replace(" ", "+")
            product.images.append(ProductImage(src=f"https://placehold.co/400x300?text={image_name}", position=0))
            db.add(product)

        dairy = Collection(title="Dairy", handle="dairy", collection_type="manual")
        beverages = Collection(title="Beverages", handle="beverages", collection_type="manual")
        db.add_all([dairy, beverages])

        tax = TaxRate(name="Standard Tax", rate=0.10, region="default", is_default=True)
        db.add(tax)
        standard_shipping = ShippingMethod(name="Standard Delivery", price=5.00, min_order_amount=50.00)
        express_shipping = ShippingMethod(name="Express Delivery", price=12.00, min_order_amount=0)
        db.add_all([standard_shipping, express_shipping])

        await db.commit()
        print("Seed data created successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
