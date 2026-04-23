"""Tests for /api/variants/lookup and PUT /api/variants/{id}."""
from decimal import Decimal

import pytest

from app.models import Product, ProductVariant
from app.services.session import create_session
from app.config import settings


async def _seed(db):
    """Create a Product + ProductVariant with barcode='4000400001234'."""
    p = Product(title="Test Beer", handle="test-beer")
    db.add(p)
    await db.flush()
    v = ProductVariant(
        product_id=p.id,
        title="500ml",
        price=Decimal("1.99"),
        pricing_type="fixed",
        vat_rate=Decimal("19.00"),
        barcode="4000400001234",
    )
    db.add(v)
    await db.commit()
    return p, v


async def _seed_manager_client(client, db):
    from app.models import User
    from app.services.password import hash_password
    u = User(
        email="mgr2@test.local",
        password_hash=hash_password("mgr-pass-2"),
        full_name="Manager Two",
        role="manager",
    )
    db.add(u)
    await db.flush()
    sess = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="test", ttl_minutes=60)
    await db.commit()
    client.cookies.set(settings.session_cookie_name, sess.id)
    return client


@pytest.mark.asyncio
async def test_lookup_by_barcode_hit(authed_client, db):
    _, v = await _seed(db)
    r = await authed_client.get("/api/variants/lookup?barcode=4000400001234")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == v.id
    assert data["barcode"] == "4000400001234"
    assert data["title"] == "500ml"


@pytest.mark.asyncio
async def test_lookup_by_barcode_miss(authed_client, db):
    r = await authed_client.get("/api/variants/lookup?barcode=9999999999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_lookup_requires_staff(client, db):
    """Unauthenticated request should be rejected."""
    await _seed(db)
    r = await client.get("/api/variants/lookup?barcode=4000400001234")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_variant_price_and_barcode(authed_client, db):
    _, v = await _seed(db)
    r = await authed_client.put(
        f"/api/variants/{v.id}",
        json={"price": "2.49", "barcode": "4000400009999"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["price"] == "2.49"
    assert data["barcode"] == "4000400009999"


@pytest.mark.asyncio
async def test_update_variant_duplicate_barcode_400(authed_client, db):
    """Assigning an already-used barcode to another variant must return 400."""
    p, v = await _seed(db)
    # Create a second variant
    v2 = ProductVariant(
        product_id=p.id,
        title="1L",
        price=Decimal("3.49"),
        pricing_type="fixed",
        vat_rate=Decimal("19.00"),
        barcode="4000400005678",
    )
    db.add(v2)
    await db.commit()
    # Try to set v2's barcode to v's barcode — should fail due to unique index
    r = await authed_client.put(
        f"/api/variants/{v2.id}",
        json={"barcode": "4000400001234"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_forbidden_for_cashier(cashier_client, db):
    _, v = await _seed(db)
    r = await cashier_client.put(
        f"/api/variants/{v.id}",
        json={"price": "0.99"},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_clears_barcode_with_null(authed_client, db):
    _, v = await _seed(db)
    r = await authed_client.put(
        f"/api/variants/{v.id}",
        json={"barcode": None},
    )
    assert r.status_code == 200
    assert r.json()["barcode"] is None
