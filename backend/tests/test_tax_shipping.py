import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant
from app.models.tax_shipping import TaxRate


async def seed_product_at_price(db, price: float):
    location = Location(name="Main Store", address="123 Main St")
    db.add(location)
    await db.flush()
    product = Product(title="Test Product", handle=f"test-product-{price}", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="Default", price=price, barcode=f"BAR{price}")
    db.add(variant)
    await db.flush()
    inv_item = InventoryItem(variant_id=variant.id)
    db.add(inv_item)
    await db.flush()
    level = InventoryLevel(inventory_item_id=inv_item.id, location_id=location.id, available=100)
    db.add(level)
    await db.commit()
    return {"variant_id": variant.id}


@pytest.mark.asyncio
async def test_create_and_list_tax_rates(client):
    response = await client.post("/api/tax-rates", json={
        "name": "GST",
        "rate": "0.1000",
        "region": "AU",
        "is_default": True,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "GST"
    assert data["is_default"] is True

    response = await client.get("/api/tax-rates")
    assert response.status_code == 200
    rates = response.json()
    assert len(rates) == 1
    assert rates[0]["name"] == "GST"


@pytest.mark.asyncio
async def test_create_and_list_shipping_methods(client):
    response = await client.post("/api/shipping-methods", json={
        "name": "Standard Delivery",
        "price": "5.00",
        "min_order_amount": "50.00",
        "is_active": True,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Standard Delivery"
    assert data["price"] == "5.00"

    response = await client.get("/api/shipping-methods")
    assert response.status_code == 200
    methods = response.json()
    assert len(methods) == 1
    assert methods[0]["name"] == "Standard Delivery"


@pytest.mark.asyncio
async def test_order_includes_tax(client, db):
    # Seed a default tax rate of 10%
    tax = TaxRate(name="Standard Tax", rate=0.10, region="default", is_default=True)
    db.add(tax)
    await db.commit()

    # Seed a product at $100
    ids = await seed_product_at_price(db, 100.00)

    response = await client.post("/api/orders", json={
        "source": "web",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["subtotal"] == "100.00"
    # tax_amount = 100.00 * 0.10 = 10.000 (Numeric(10,2) * Numeric(5,4) yields variable scale)
    assert float(data["tax_amount"]) == pytest.approx(10.0)
    assert float(data["total_price"]) == pytest.approx(110.0)


@pytest.mark.asyncio
async def test_order_no_tax_when_no_default(client, db):
    """Without a default tax rate, tax_amount should be 0 (backward compat)."""
    ids = await seed_product_at_price(db, 50.00)

    response = await client.post("/api/orders", json={
        "source": "web",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 2}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["subtotal"] == "100.00"
    assert data["tax_amount"] == "0"
    assert data["total_price"] == "100.00"


@pytest.mark.asyncio
async def test_order_with_shipping_method(client, db):
    ids = await seed_product_at_price(db, 10.00)

    shipping_resp = await client.post("/api/shipping-methods", json={
        "name": "Express",
        "price": "12.00",
        "min_order_amount": "0",
        "is_active": True,
    })
    shipping_id = shipping_resp.json()["id"]

    response = await client.post("/api/orders", json={
        "source": "web",
        "shipping_method_id": shipping_id,
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["subtotal"] == "10.00"
    assert data["shipping_amount"] == "12.00"
    assert data["total_price"] == "22.00"


@pytest.mark.asyncio
async def test_order_free_shipping_threshold(client, db):
    """When subtotal >= min_order_amount, shipping should be free."""
    ids = await seed_product_at_price(db, 60.00)

    shipping_resp = await client.post("/api/shipping-methods", json={
        "name": "Standard",
        "price": "5.00",
        "min_order_amount": "50.00",
        "is_active": True,
    })
    shipping_id = shipping_resp.json()["id"]

    response = await client.post("/api/orders", json={
        "source": "web",
        "shipping_method_id": shipping_id,
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["subtotal"] == "60.00"
    assert data["shipping_amount"] == "0"
    assert data["total_price"] == "60.00"
