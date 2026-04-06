# Shopify Parity Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 6 critical gaps between OpenMarket and Shopify: product images in UI, customer accounts, admin analytics, tax/shipping calculation, POS receipts/returns, and CI/CD + DB indexes.

**Architecture:** Each feature is an independent vertical slice (backend API + frontend UI). All frontend apps use React with inline CSS-in-JS and the shared design token system in `@openmarket/shared`. Backend is async FastAPI with SQLAlchemy models, Pydantic schemas, and service-layer business logic. Tests use pytest-asyncio with httpx AsyncClient against a test DB on port 5433.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy (async) / PostgreSQL 16 / React 18 / TypeScript / pnpm monorepo / Docker Compose / Nginx

---

## Task 1: Product Images in Store UI

**Files:**
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/ShopPage.tsx`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/CartCheckoutPage.tsx`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/api.ts`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/schemas/product.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/api/products.py`

### Context

The `Product` model already has `images` relationship and `ProductImage` model with `src` and `position` fields. The `ProductListWithPrice` schema returned by `GET /products` does NOT include images — only `id, title, handle, product_type, status, tags, min_price`. The full `ProductOut` schema (returned by `GET /products/{id}`) includes images. The store's `ShopPage.tsx` displays product cards in a grid with no images — just title, type, and price.

### Steps

- [ ] **Step 1: Add `image_url` to product list API response**

In `/Users/huijokim/personal/openmarket/backend/app/schemas/product.py`, add `image_url` field to `ProductListWithPriceOut`:

```python
class ProductListWithPriceOut(BaseModel):
    id: int
    title: str
    handle: str
    product_type: str
    status: str
    tags: list[str]
    min_price: Decimal | None = None
    image_url: str | None = None  # <-- add this

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Populate `image_url` in the product list query**

In `/Users/huijokim/personal/openmarket/backend/app/api/products.py`, modify the `list_products` endpoint. Currently it does:

```python
result = await db.execute(query.order_by(Product.id))
products = result.scalars().all()
```

Replace with a query that also fetches the first image for each product:

```python
from sqlalchemy.orm import selectinload

result = await db.execute(query.options(selectinload(Product.images)).order_by(Product.id))
products = result.scalars().unique().all()
out = []
for p in products:
    min_price = min((v.price for v in p.variants), default=None) if p.variants else None
    sorted_images = sorted(p.images, key=lambda img: img.position)
    out.append({
        "id": p.id, "title": p.title, "handle": p.handle,
        "product_type": p.product_type, "status": p.status, "tags": p.tags or [],
        "min_price": min_price,
        "image_url": sorted_images[0].src if sorted_images else None,
    })
return out
```

Note: The current list endpoint already computes `min_price` manually. Read the existing code carefully — it uses `selectinload(Product.variants)` already. Just add `selectinload(Product.images)` and the image_url extraction.

- [ ] **Step 3: Update the frontend `ProductListWithPrice` type**

In `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/types.ts`, add to `ProductListWithPrice`:

```typescript
export interface ProductListWithPrice {
  id: number;
  title: string;
  handle: string;
  product_type: string;
  status: string;
  tags: string[];
  min_price: string | null;
  image_url: string | null;  // <-- add this
}
```

- [ ] **Step 4: Show product images in store product cards**

In `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/ShopPage.tsx`, add an image element to each product card. Find the product card `<div>` inside the `.map()` that renders `p.product_type`, `p.title`, and `p.min_price`. Add an image before the product type:

```tsx
{p.image_url ? (
  <img src={p.image_url} alt={p.title}
    style={{ width: "100%", height: 160, objectFit: "cover", borderRadius: radius.sm, marginBottom: spacing.sm }} />
) : (
  <div style={{ width: "100%", height: 160, background: colors.surfaceMuted, borderRadius: radius.sm, marginBottom: spacing.sm,
    display: "flex", alignItems: "center", justifyContent: "center", color: colors.textDisabled, fontSize: "14px" }}>
    No image
  </div>
)}
```

- [ ] **Step 5: Show images in product detail panel**

In the same file's detail panel section (the `selectedProduct && (...)` block), add an image gallery before the `<h2>` title. The full product already has `images: ProductImage[]`:

```tsx
{selectedProduct.images.length > 0 && (
  <img src={selectedProduct.images.sort((a, b) => a.position - b.position)[0].src} alt={selectedProduct.title}
    style={{ width: "100%", height: 200, objectFit: "cover", borderRadius: radius.sm, marginBottom: spacing.md }} />
)}
```

- [ ] **Step 6: Show product images in cart line items**

In `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/CartCheckoutPage.tsx`, the `CartItem` type already holds the full `product` object including `images`. In the cart items `.map()`, add a small thumbnail before the product name:

```tsx
<div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
  {item.product.images.length > 0 ? (
    <img src={item.product.images[0].src} alt={item.product.title}
      style={{ width: 48, height: 48, objectFit: "cover", borderRadius: radius.sm, flexShrink: 0 }} />
  ) : (
    <div style={{ width: 48, height: 48, background: colors.surfaceMuted, borderRadius: radius.sm, flexShrink: 0 }} />
  )}
  <div>
    <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.product.title}</div>
    <div style={{ color: colors.textSecondary, fontSize: "13px" }}>{item.variant.title} &middot; ${item.variant.price}</div>
  </div>
</div>
```

- [ ] **Step 7: Add seed data with product images**

In `/Users/huijokim/personal/openmarket/backend/seed.py`, add `ProductImage` imports and create image records for each product. Use placeholder URLs:

```python
from app.models.product import Product, ProductVariant, ProductImage

# After creating each product, add:
img = ProductImage(product_id=product.id, src="https://placehold.co/400x300?text=Milk", position=0)
db.add(img)
```

Add images for all 5 seed products.

- [ ] **Step 8: Write backend test for image_url in product list**

In `/Users/huijokim/personal/openmarket/backend/tests/test_products.py`, add a test:

```python
@pytest.mark.asyncio
async def test_list_products_includes_image_url(client, db):
    from app.models.product import Product, ProductVariant, ProductImage
    p = Product(title="Test", handle="test-img", status="active", tags=[])
    db.add(p)
    await db.flush()
    v = ProductVariant(product_id=p.id, title="Default", price=1.00)
    db.add(v)
    img = ProductImage(product_id=p.id, src="https://example.com/img.jpg", position=0)
    db.add(img)
    await db.commit()
    response = await client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    product = next(p for p in data if p["handle"] == "test-img")
    assert product["image_url"] == "https://example.com/img.jpg"
```

- [ ] **Step 9: Run tests**

```bash
cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_products.py -v
```

Expected: All tests pass including the new image_url test.

- [ ] **Step 10: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add backend/app/schemas/product.py backend/app/api/products.py backend/seed.py backend/tests/test_products.py frontend/packages/shared/src/types.ts frontend/packages/store/src/pages/ShopPage.tsx frontend/packages/store/src/pages/CartCheckoutPage.tsx
git commit -m "feat: display product images in store product cards, detail panel, and cart"
```

---

## Task 2: Customer Accounts (Backend)

**Files:**
- Modify: `/Users/huijokim/personal/openmarket/backend/app/models/customer.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/schemas/customer.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/api/customers.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/services/order.py`
- Create: `/Users/huijokim/personal/openmarket/backend/tests/test_customer_orders.py`

### Context

The `Customer` model has `id, email, first_name, last_name, phone, addresses`. Orders have a `customer_id` FK but it's always null for web orders (only name/phone are passed). There's no way to look up a customer's orders. There's no customer update endpoint.

### Steps

- [ ] **Step 1: Add customer update and order-history endpoints**

In `/Users/huijokim/personal/openmarket/backend/app/schemas/customer.py`, add:

```python
class CustomerUpdate(BaseModel):
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
```

- [ ] **Step 2: Add PUT /customers/{id} and GET /customers/{id}/orders**

In `/Users/huijokim/personal/openmarket/backend/app/api/customers.py`, add:

```python
from app.schemas.customer import CustomerUpdate
from app.models.order import Order
from app.schemas.order import OrderListOut

@router.put("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(customer_id: int, body: CustomerUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id).options(selectinload(Customer.addresses)))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    await db.commit()
    await db.refresh(customer, ["addresses"])
    return customer


@router.get("/customers/{customer_id}/orders", response_model=list[OrderListOut])
async def customer_orders(customer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())
    )
    return result.scalars().all()
```

- [ ] **Step 3: Add customer lookup by email or phone**

In the same file, add a lookup endpoint:

```python
@router.get("/customers/lookup", response_model=CustomerOut)
async def lookup_customer(
    email: str | None = None,
    phone: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not email and not phone:
        raise HTTPException(status_code=400, detail="Provide email or phone")
    query = select(Customer).options(selectinload(Customer.addresses))
    if email:
        query = query.where(Customer.email == email)
    if phone:
        query = query.where(Customer.phone == phone)
    result = await db.execute(query)
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer
```

**Important:** Place this route BEFORE the `/{customer_id}` routes to avoid path conflicts.

- [ ] **Step 4: Auto-create/link customer on order creation**

In `/Users/huijokim/personal/openmarket/backend/app/services/order.py`, modify `create_order` to auto-create or link a customer when `customer_name` and `customer_phone` are provided. Add these parameters to the function signature:

```python
async def create_order(
    db: AsyncSession,
    source: str,
    line_items_data: list[dict],
    customer_id: int | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    shipping_address: dict | None = None,
) -> Order:
```

Before creating the order, add customer resolution:

```python
from app.models.customer import Customer

if customer_id is None and customer_phone:
    result = await db.execute(select(Customer).where(Customer.phone == customer_phone))
    existing = result.scalar_one_or_none()
    if existing:
        customer_id = existing.id
    elif customer_name:
        parts = customer_name.strip().split(" ", 1)
        new_customer = Customer(
            first_name=parts[0],
            last_name=parts[1] if len(parts) > 1 else "",
            phone=customer_phone,
        )
        db.add(new_customer)
        await db.flush()
        customer_id = new_customer.id
```

Also update the call site in `/Users/huijokim/personal/openmarket/backend/app/api/orders.py`:

```python
order = await create_order(
    db=db,
    source=body.source,
    line_items_data=[li.model_dump() for li in body.line_items],
    customer_id=body.customer_id,
    customer_name=body.customer_name,
    customer_phone=body.customer_phone,
    shipping_address=body.shipping_address,
)
```

- [ ] **Step 5: Write tests**

Create `/Users/huijokim/personal/openmarket/backend/tests/test_customer_orders.py`:

```python
import pytest
from app.models.customer import Customer
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_customer_and_product(db):
    customer = Customer(first_name="Jane", last_name="Doe", phone="555-9999", email="jane@test.com")
    db.add(customer)
    location = Location(name="Store", address="1 Main")
    db.add(location)
    await db.flush()
    product = Product(title="Apple", handle="apple", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="1kg", price=3.00)
    db.add(variant)
    await db.flush()
    inv = InventoryItem(variant_id=variant.id)
    db.add(inv)
    await db.flush()
    level = InventoryLevel(inventory_item_id=inv.id, location_id=location.id, available=100)
    db.add(level)
    await db.commit()
    return {"customer_id": customer.id, "variant_id": variant.id}


@pytest.mark.asyncio
async def test_update_customer(client, db):
    c = Customer(first_name="Old", last_name="Name", phone="111")
    db.add(c)
    await db.commit()
    resp = await client.put(f"/api/customers/{c.id}", json={"first_name": "New"})
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "New"


@pytest.mark.asyncio
async def test_customer_order_history(client, db):
    ids = await seed_customer_and_product(db)
    await client.post("/api/orders", json={
        "source": "web", "customer_id": ids["customer_id"],
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    resp = await client.get(f"/api/customers/{ids['customer_id']}/orders")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_lookup_customer_by_phone(client, db):
    c = Customer(first_name="Find", last_name="Me", phone="555-FIND")
    db.add(c)
    await db.commit()
    resp = await client.get("/api/customers/lookup?phone=555-FIND")
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Find"


@pytest.mark.asyncio
async def test_order_auto_creates_customer(client, db):
    ids = await seed_customer_and_product(db)
    resp = await client.post("/api/orders", json={
        "source": "web", "customer_name": "Auto User", "customer_phone": "555-AUTO",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    assert resp.status_code == 201
    assert resp.json()["customer_id"] is not None
    cust_resp = await client.get("/api/customers/lookup?phone=555-AUTO")
    assert cust_resp.status_code == 200
    assert cust_resp.json()["first_name"] == "Auto"
```

- [ ] **Step 6: Run tests**

```bash
cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_customer_orders.py tests/test_orders.py -v
```

Expected: All pass. Existing order tests still pass.

- [ ] **Step 7: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add backend/app/schemas/customer.py backend/app/api/customers.py backend/app/api/orders.py backend/app/services/order.py backend/tests/test_customer_orders.py
git commit -m "feat: customer accounts with update, lookup, order history, and auto-creation"
```

---

## Task 3: Customer Accounts (Frontend - Store)

**Files:**
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/api.ts`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/types.ts`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/store/src/App.tsx`
- Create: `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/AccountPage.tsx`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/CartCheckoutPage.tsx`

### Context

There is no customer login. The store has 3 pages: ShopPage, CartCheckoutPage, OrderStatusPage. We'll add a simple phone-based customer lookup (no auth yet — just identify by phone). This lets customers see their order history and pre-fill checkout.

### Steps

- [ ] **Step 1: Add API methods for customer lookup and order history**

In `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/api.ts`, add to the `customers` object:

```typescript
customers: {
    list: () => request<import("./types").Customer[]>("/customers"),
    get: (id: number) => request<import("./types").Customer>(`/customers/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Customer>("/customers", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Customer>(`/customers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    lookup: (params: { email?: string; phone?: string }) => {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v != null)) as Record<string, string>
      ).toString();
      return request<import("./types").Customer>(`/customers/lookup?${qs}`);
    },
    orders: (id: number) =>
      request<import("./types").OrderListItem[]>(`/customers/${id}/orders`),
  },
```

- [ ] **Step 2: Create AccountPage component**

Create `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/AccountPage.tsx`:

```tsx
import { useState } from "react";
import { api, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Customer, OrderListItem } from "@openmarket/shared";

export function AccountPage() {
  const [phone, setPhone] = useState("");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const lookupCustomer = async () => {
    if (!phone.trim()) return;
    setLoading(true);
    setError("");
    try {
      const c = await api.customers.lookup({ phone: phone.trim() });
      setCustomer(c);
      const o = await api.customers.orders(c.id);
      setOrders(o);
    } catch {
      setError("No account found with that phone number.");
      setCustomer(null);
      setOrders([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ ...baseStyles.container, maxWidth: 600 }}>
      <h2 style={{ marginBottom: spacing.lg }}>My Account</h2>

      {!customer ? (
        <div style={baseStyles.card}>
          <p style={{ color: colors.textSecondary, fontSize: "14px", marginBottom: spacing.md }}>
            Enter your phone number to view your account and order history.
          </p>
          <div style={{ display: "flex", gap: "8px" }}>
            <input placeholder="Phone number" value={phone}
              onChange={(e) => setPhone(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && lookupCustomer()}
              style={baseStyles.input} />
            <Button variant="primary" onClick={lookupCustomer} loading={loading} style={{ flexShrink: 0 }}>
              Look Up
            </Button>
          </div>
          {error && (
            <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "8px 12px",
              borderRadius: radius.sm, fontSize: "14px", marginTop: spacing.sm }}>{error}</div>
          )}
        </div>
      ) : (
        <>
          <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
            <h3 style={{ margin: "0 0 8px", fontSize: "16px" }}>Profile</h3>
            <div style={{ fontSize: "14px", color: colors.textSecondary }}>
              <p style={{ margin: "4px 0" }}>{customer.first_name} {customer.last_name}</p>
              {customer.email && <p style={{ margin: "4px 0" }}>{customer.email}</p>}
              <p style={{ margin: "4px 0" }}>{customer.phone}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => { setCustomer(null); setOrders([]); }}
              style={{ marginTop: spacing.sm }}>Sign Out</Button>
          </div>

          <div style={baseStyles.card}>
            <h3 style={{ margin: "0 0 16px", fontSize: "16px" }}>Order History</h3>
            {loading ? <Spinner label="Loading orders..." /> : orders.length === 0 ? (
              <p style={{ color: colors.textSecondary, fontSize: "14px" }}>No orders yet.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {orders.map((o) => (
                  <div key={o.id} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "10px 12px", background: colors.surfaceMuted, borderRadius: radius.sm,
                  }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "14px" }}>{o.order_number}</div>
                      <div style={{ color: colors.textSecondary, fontSize: "13px" }}>
                        {new Date(o.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontWeight: 600, color: colors.brand }}>${o.total_price}</div>
                      <span style={{
                        padding: "2px 8px", borderRadius: "4px", fontSize: "11px", fontWeight: 600,
                        background: o.fulfillment_status === "fulfilled" ? colors.successSurface : colors.warningSurface,
                        color: o.fulfillment_status === "fulfilled" ? colors.success : colors.warning,
                      }}>{o.fulfillment_status}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add Account route and nav link**

In `/Users/huijokim/personal/openmarket/frontend/packages/store/src/App.tsx`, import and add the route:

```tsx
import { AccountPage } from "./pages/AccountPage";

// In NavBar, add before closing </nav>:
<Link to="/account" style={baseStyles.navLink}>Account</Link>

// In Routes, add:
<Route path="/account" element={<AccountPage />} />
```

- [ ] **Step 4: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add frontend/packages/shared/src/api.ts frontend/packages/store/src/pages/AccountPage.tsx frontend/packages/store/src/App.tsx
git commit -m "feat: add customer account page with phone lookup and order history"
```

---

## Task 4: Admin Analytics Dashboard

**Files:**
- Create: `/Users/huijokim/personal/openmarket/backend/app/api/analytics.py`
- Create: `/Users/huijokim/personal/openmarket/backend/app/schemas/analytics.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/main.py`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/api.ts`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/types.ts`
- Create: `/Users/huijokim/personal/openmarket/frontend/packages/admin/src/pages/AnalyticsPage.tsx`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/admin/src/App.tsx`
- Create: `/Users/huijokim/personal/openmarket/backend/tests/test_analytics.py`

### Context

There are no analytics endpoints. The admin has only Products & Orders pages. Orders have `total_price`, `source`, `created_at`, and `fulfillment_status`. We need to add a backend analytics endpoint and a frontend dashboard with key metrics.

### Steps

- [ ] **Step 1: Create analytics schemas**

Create `/Users/huijokim/personal/openmarket/backend/app/schemas/analytics.py`:

```python
from decimal import Decimal
from pydantic import BaseModel


class DailySales(BaseModel):
    date: str
    order_count: int
    revenue: Decimal


class TopProduct(BaseModel):
    title: str
    quantity_sold: int
    revenue: Decimal


class AnalyticsSummary(BaseModel):
    total_revenue: Decimal
    total_orders: int
    average_order_value: Decimal
    daily_sales: list[DailySales]
    top_products: list[TopProduct]
    orders_by_source: dict[str, int]
```

- [ ] **Step 2: Create analytics API endpoint**

Create `/Users/huijokim/personal/openmarket/backend/app/api/analytics.py`:

```python
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.order import Order, LineItem
from app.schemas.analytics import AnalyticsSummary, DailySales, TopProduct

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    # Total revenue and order count
    totals = await db.execute(
        select(
            func.coalesce(func.sum(Order.total_price), 0).label("revenue"),
            func.count(Order.id).label("count"),
        ).where(Order.created_at >= since)
    )
    row = totals.one()
    total_revenue = row.revenue
    total_orders = row.count
    avg_order = total_revenue / total_orders if total_orders > 0 else 0

    # Daily sales
    daily_query = await db.execute(
        select(
            cast(Order.created_at, Date).label("date"),
            func.count(Order.id).label("order_count"),
            func.sum(Order.total_price).label("revenue"),
        )
        .where(Order.created_at >= since)
        .group_by(cast(Order.created_at, Date))
        .order_by(cast(Order.created_at, Date))
    )
    daily_sales = [
        DailySales(date=str(r.date), order_count=r.order_count, revenue=r.revenue)
        for r in daily_query.all()
    ]

    # Top products by quantity
    top_query = await db.execute(
        select(
            LineItem.title,
            func.sum(LineItem.quantity).label("quantity_sold"),
            func.sum(LineItem.price * LineItem.quantity).label("revenue"),
        )
        .join(Order, LineItem.order_id == Order.id)
        .where(Order.created_at >= since)
        .group_by(LineItem.title)
        .order_by(func.sum(LineItem.quantity).desc())
        .limit(10)
    )
    top_products = [
        TopProduct(title=r.title, quantity_sold=r.quantity_sold, revenue=r.revenue)
        for r in top_query.all()
    ]

    # Orders by source
    source_query = await db.execute(
        select(Order.source, func.count(Order.id).label("count"))
        .where(Order.created_at >= since)
        .group_by(Order.source)
    )
    orders_by_source = {r.source: r.count for r in source_query.all()}

    return AnalyticsSummary(
        total_revenue=total_revenue,
        total_orders=total_orders,
        average_order_value=avg_order,
        daily_sales=daily_sales,
        top_products=top_products,
        orders_by_source=orders_by_source,
    )
```

- [ ] **Step 3: Register analytics router**

In `/Users/huijokim/personal/openmarket/backend/app/main.py`, add:

```python
from app.api.analytics import router as analytics_router

# After the last include_router call:
app.include_router(analytics_router)
```

- [ ] **Step 4: Write analytics test**

Create `/Users/huijokim/personal/openmarket/backend/tests/test_analytics.py`:

```python
import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_orders(db):
    location = Location(name="Store", address="1 Main")
    db.add(location)
    await db.flush()
    product = Product(title="Widget", handle="widget", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="Standard", price=10.00)
    db.add(variant)
    await db.flush()
    inv = InventoryItem(variant_id=variant.id)
    db.add(inv)
    await db.flush()
    level = InventoryLevel(inventory_item_id=inv.id, location_id=location.id, available=1000)
    db.add(level)
    await db.commit()
    return {"variant_id": variant.id}


@pytest.mark.asyncio
async def test_analytics_summary_empty(client, db):
    resp = await client.get("/api/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_orders"] == 0
    assert data["total_revenue"] == "0"


@pytest.mark.asyncio
async def test_analytics_summary_with_orders(client, db):
    ids = await seed_orders(db)
    for _ in range(3):
        await client.post("/api/orders", json={
            "source": "pos",
            "line_items": [{"variant_id": ids["variant_id"], "quantity": 2}],
        })
    resp = await client.get("/api/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_orders"] == 3
    assert float(data["total_revenue"]) == 60.0
    assert float(data["average_order_value"]) == 20.0
    assert len(data["top_products"]) == 1
    assert data["orders_by_source"]["pos"] == 3
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_analytics.py -v
```

Expected: All pass.

- [ ] **Step 6: Add analytics types and API to frontend**

In `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/types.ts`, add:

```typescript
export interface DailySales {
  date: string;
  order_count: number;
  revenue: string;
}

export interface TopProduct {
  title: string;
  quantity_sold: number;
  revenue: string;
}

export interface AnalyticsSummary {
  total_revenue: string;
  total_orders: number;
  average_order_value: string;
  daily_sales: DailySales[];
  top_products: TopProduct[];
  orders_by_source: Record<string, number>;
}
```

In `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/api.ts`, add:

```typescript
analytics: {
  summary: (days?: number) =>
    request<import("./types").AnalyticsSummary>(`/analytics/summary${days ? `?days=${days}` : ""}`),
},
```

- [ ] **Step 7: Create AnalyticsPage**

Create `/Users/huijokim/personal/openmarket/frontend/packages/admin/src/pages/AnalyticsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api, Spinner, Button, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { AnalyticsSummary } from "@openmarket/shared";

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    api.analytics.summary(days).then(setData).finally(() => setLoading(false));
  }, [days]);

  if (loading) return <div style={baseStyles.container}><Spinner label="Loading analytics..." /></div>;
  if (!data) return null;

  const metricCard = (label: string, value: string, color?: string) => (
    <div style={{ ...baseStyles.card, flex: 1, textAlign: "center" }}>
      <div style={{ fontSize: "13px", color: colors.textSecondary, marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.5px" }}>{label}</div>
      <div style={{ fontSize: "28px", fontWeight: 700, color: color || colors.textPrimary }}>{value}</div>
    </div>
  );

  const maxRevenue = Math.max(...data.daily_sales.map((d) => parseFloat(d.revenue)), 1);

  return (
    <div style={baseStyles.container}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
        <h2 style={{ margin: 0 }}>Analytics</h2>
        <div style={{ display: "flex", gap: "8px" }}>
          {[7, 30, 90].map((d) => (
            <Button key={d} variant={days === d ? "primary" : "secondary"} size="sm" onClick={() => setDays(d)}>
              {d}d
            </Button>
          ))}
        </div>
      </div>

      {/* Metric Cards */}
      <div style={{ display: "flex", gap: spacing.md, marginBottom: spacing.lg }}>
        {metricCard("Revenue", `$${parseFloat(data.total_revenue).toLocaleString("en-US", { minimumFractionDigits: 2 })}`, colors.brand)}
        {metricCard("Orders", String(data.total_orders))}
        {metricCard("Avg Order", `$${parseFloat(data.average_order_value).toFixed(2)}`)}
      </div>

      {/* Daily Sales Bar Chart */}
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <h3 style={{ margin: "0 0 16px", fontSize: "15px" }}>Daily Sales</h3>
        {data.daily_sales.length === 0 ? (
          <p style={{ color: colors.textSecondary, fontSize: "14px" }}>No sales in this period.</p>
        ) : (
          <div style={{ display: "flex", alignItems: "flex-end", gap: "2px", height: 120 }}>
            {data.daily_sales.map((d) => {
              const height = (parseFloat(d.revenue) / maxRevenue) * 100;
              return (
                <div key={d.date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}
                  title={`${d.date}: $${parseFloat(d.revenue).toFixed(2)} (${d.order_count} orders)`}>
                  <div style={{
                    width: "100%", maxWidth: 24, height: `${Math.max(height, 2)}%`,
                    background: colors.brand, borderRadius: "3px 3px 0 0",
                  }} />
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: spacing.md }}>
        {/* Top Products */}
        <div style={{ ...baseStyles.card, flex: 2 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: "15px" }}>Top Products</h3>
          {data.top_products.length === 0 ? (
            <p style={{ color: colors.textSecondary, fontSize: "14px" }}>No sales yet.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
              <thead>
                <tr style={{ textAlign: "left", color: colors.textSecondary }}>
                  <th style={{ padding: "6px 0" }}>Product</th>
                  <th style={{ padding: "6px 0" }}>Qty Sold</th>
                  <th style={{ padding: "6px 0" }}>Revenue</th>
                </tr>
              </thead>
              <tbody>
                {data.top_products.map((p) => (
                  <tr key={p.title} style={{ borderTop: `1px solid ${colors.border}` }}>
                    <td style={{ padding: "8px 0", fontWeight: 500 }}>{p.title}</td>
                    <td style={{ padding: "8px 0" }}>{p.quantity_sold}</td>
                    <td style={{ padding: "8px 0", fontWeight: 600, color: colors.brand }}>${parseFloat(p.revenue).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Orders by Source */}
        <div style={{ ...baseStyles.card, flex: 1 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: "15px" }}>Orders by Source</h3>
          {Object.entries(data.orders_by_source).map(([source, count]) => (
            <div key={source} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: `1px solid ${colors.border}` }}>
              <span style={{
                padding: "2px 8px", borderRadius: "4px", fontSize: "12px", fontWeight: 600,
                background: source === "pos" ? colors.brandLight : colors.warningSurface,
                color: source === "pos" ? colors.brand : colors.warning,
              }}>{source.toUpperCase()}</span>
              <span style={{ fontWeight: 600 }}>{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Add Analytics route to admin**

In `/Users/huijokim/personal/openmarket/frontend/packages/admin/src/App.tsx`:

```tsx
import { AnalyticsPage } from "./pages/AnalyticsPage";

// In nav, add link:
<Link to="/analytics" style={linkStyle("/analytics")}>Analytics</Link>

// In Routes, add:
<Route path="/analytics" element={<AnalyticsPage />} />

// Change default redirect from /products to /analytics:
<Route path="/" element={<Navigate to="/analytics" replace />} />
```

- [ ] **Step 9: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add backend/app/schemas/analytics.py backend/app/api/analytics.py backend/app/main.py backend/tests/test_analytics.py frontend/packages/shared/src/types.ts frontend/packages/shared/src/api.ts frontend/packages/admin/src/pages/AnalyticsPage.tsx frontend/packages/admin/src/App.tsx
git commit -m "feat: add admin analytics dashboard with revenue, daily sales, and top products"
```

---

## Task 5: Tax and Shipping Calculation (Backend)

**Files:**
- Create: `/Users/huijokim/personal/openmarket/backend/app/models/tax_shipping.py`
- Create: `/Users/huijokim/personal/openmarket/backend/app/schemas/tax_shipping.py`
- Create: `/Users/huijokim/personal/openmarket/backend/app/api/tax_shipping.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/models/__init__.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/main.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/models/order.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/schemas/order.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/services/order.py`
- Create: `/Users/huijokim/personal/openmarket/backend/tests/test_tax_shipping.py`

### Context

Orders currently have only `total_price`. No tax or shipping is calculated. We'll add TaxRate and ShippingMethod models, a calculation endpoint, and include tax/shipping in order totals.

### Steps

- [ ] **Step 1: Create tax and shipping models**

Create `/Users/huijokim/personal/openmarket/backend/app/models/tax_shipping.py`:

```python
from sqlalchemy import Column, Integer, Numeric, String, Boolean

from app.database import Base


class TaxRate(Base):
    __tablename__ = "tax_rates"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    rate = Column(Numeric(5, 4), nullable=False)  # e.g. 0.1000 for 10%
    region = Column(String, default="")
    is_default = Column(Boolean, default=False)


class ShippingMethod(Base):
    __tablename__ = "shipping_methods"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    min_order_amount = Column(Numeric(10, 2), default=0)  # free shipping threshold
    is_active = Column(Boolean, default=True)
```

- [ ] **Step 2: Register models in `__init__.py`**

Read `/Users/huijokim/personal/openmarket/backend/app/models/__init__.py` and add:

```python
from app.models.tax_shipping import TaxRate, ShippingMethod  # noqa: F401
```

- [ ] **Step 3: Add tax/shipping fields to Order model**

In `/Users/huijokim/personal/openmarket/backend/app/models/order.py`, add columns to the `Order` class:

```python
tax_amount = Column(Numeric(10, 2), default=0)
shipping_amount = Column(Numeric(10, 2), default=0)
subtotal = Column(Numeric(10, 2), nullable=False)
```

- [ ] **Step 4: Update order schemas**

In `/Users/huijokim/personal/openmarket/backend/app/schemas/order.py`:

Add to `OrderCreate`:
```python
shipping_method_id: int | None = None
```

Add to `OrderOut`:
```python
subtotal: Decimal
tax_amount: Decimal
shipping_amount: Decimal
```

Add to `OrderListOut`:
```python
# total_price already exists, no changes needed
```

- [ ] **Step 5: Create tax/shipping schemas**

Create `/Users/huijokim/personal/openmarket/backend/app/schemas/tax_shipping.py`:

```python
from decimal import Decimal
from pydantic import BaseModel


class TaxRateOut(BaseModel):
    id: int
    name: str
    rate: Decimal
    region: str
    is_default: bool

    model_config = {"from_attributes": True}


class TaxRateCreate(BaseModel):
    name: str
    rate: Decimal
    region: str = ""
    is_default: bool = False


class ShippingMethodOut(BaseModel):
    id: int
    name: str
    price: Decimal
    min_order_amount: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


class ShippingMethodCreate(BaseModel):
    name: str
    price: Decimal
    min_order_amount: Decimal = Decimal("0")
    is_active: bool = True


class OrderCalculation(BaseModel):
    subtotal: Decimal
    tax_rate_name: str
    tax_rate: Decimal
    tax_amount: Decimal
    shipping_method_name: str
    shipping_amount: Decimal
    total: Decimal
```

- [ ] **Step 6: Create tax/shipping API**

Create `/Users/huijokim/personal/openmarket/backend/app/api/tax_shipping.py`:

```python
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.tax_shipping import TaxRate, ShippingMethod
from app.schemas.tax_shipping import (
    TaxRateOut, TaxRateCreate, ShippingMethodOut, ShippingMethodCreate, OrderCalculation,
)

router = APIRouter(prefix="/api", tags=["tax-shipping"])


@router.get("/tax-rates", response_model=list[TaxRateOut])
async def list_tax_rates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaxRate))
    return result.scalars().all()


@router.post("/tax-rates", response_model=TaxRateOut, status_code=201)
async def create_tax_rate(body: TaxRateCreate, db: AsyncSession = Depends(get_db)):
    rate = TaxRate(**body.model_dump())
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.get("/shipping-methods", response_model=list[ShippingMethodOut])
async def list_shipping_methods(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ShippingMethod).where(ShippingMethod.is_active == True))
    return result.scalars().all()


@router.post("/shipping-methods", response_model=ShippingMethodOut, status_code=201)
async def create_shipping_method(body: ShippingMethodCreate, db: AsyncSession = Depends(get_db)):
    method = ShippingMethod(**body.model_dump())
    db.add(method)
    await db.commit()
    await db.refresh(method)
    return method


@router.post("/calculate-order", response_model=OrderCalculation)
async def calculate_order(
    subtotal: Decimal,
    shipping_method_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    # Get default tax rate
    result = await db.execute(select(TaxRate).where(TaxRate.is_default == True))
    tax_rate = result.scalar_one_or_none()
    tax_rate_value = tax_rate.rate if tax_rate else Decimal("0")
    tax_name = tax_rate.name if tax_rate else "No tax"
    tax_amount = (subtotal * tax_rate_value).quantize(Decimal("0.01"))

    # Get shipping
    shipping_amount = Decimal("0")
    shipping_name = "No shipping"
    if shipping_method_id:
        result = await db.execute(select(ShippingMethod).where(ShippingMethod.id == shipping_method_id))
        method = result.scalar_one_or_none()
        if method:
            shipping_name = method.name
            if method.min_order_amount > 0 and subtotal >= method.min_order_amount:
                shipping_amount = Decimal("0")  # Free shipping threshold met
            else:
                shipping_amount = method.price

    return OrderCalculation(
        subtotal=subtotal,
        tax_rate_name=tax_name,
        tax_rate=tax_rate_value,
        tax_amount=tax_amount,
        shipping_method_name=shipping_name,
        shipping_amount=shipping_amount,
        total=subtotal + tax_amount + shipping_amount,
    )
```

- [ ] **Step 7: Register tax/shipping router**

In `/Users/huijokim/personal/openmarket/backend/app/main.py`:

```python
from app.api.tax_shipping import router as tax_shipping_router
app.include_router(tax_shipping_router)
```

- [ ] **Step 8: Update order service to include tax/shipping**

In `/Users/huijokim/personal/openmarket/backend/app/services/order.py`, update `create_order` to accept and store tax/shipping:

Add parameters:
```python
async def create_order(
    db: AsyncSession,
    source: str,
    line_items_data: list[dict],
    customer_id: int | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    shipping_address: dict | None = None,
    shipping_method_id: int | None = None,
) -> Order:
```

After computing `total` from line items, add tax/shipping calculation:

```python
from app.models.tax_shipping import TaxRate, ShippingMethod
from decimal import Decimal

subtotal = total  # `total` is the sum of line item prices

# Apply default tax
tax_result = await db.execute(select(TaxRate).where(TaxRate.is_default == True))
tax_rate_row = tax_result.scalar_one_or_none()
tax_amount = (subtotal * tax_rate_row.rate).quantize(Decimal("0.01")) if tax_rate_row else Decimal("0")

# Apply shipping
shipping_amount = Decimal("0")
if shipping_method_id:
    ship_result = await db.execute(select(ShippingMethod).where(ShippingMethod.id == shipping_method_id))
    method = ship_result.scalar_one_or_none()
    if method:
        if method.min_order_amount > 0 and subtotal >= method.min_order_amount:
            shipping_amount = Decimal("0")
        else:
            shipping_amount = method.price

total = subtotal + tax_amount + shipping_amount
```

Update the Order creation:
```python
order = Order(
    order_number=order_number,
    customer_id=customer_id,
    source=source,
    fulfillment_status="fulfilled" if source == "pos" else "unfulfilled",
    subtotal=subtotal,
    tax_amount=tax_amount,
    shipping_amount=shipping_amount,
    total_price=total,
    shipping_address=shipping_address,
)
```

Also update the call site in `orders.py` to pass `shipping_method_id=body.shipping_method_id`.

- [ ] **Step 9: Add seed data for tax rates and shipping methods**

In `/Users/huijokim/personal/openmarket/backend/seed.py`, add:

```python
from app.models.tax_shipping import TaxRate, ShippingMethod

tax = TaxRate(name="Standard Tax", rate=0.10, region="default", is_default=True)
db.add(tax)

standard_shipping = ShippingMethod(name="Standard Delivery", price=5.00, min_order_amount=50.00, is_active=True)
express_shipping = ShippingMethod(name="Express Delivery", price=12.00, min_order_amount=0, is_active=True)
db.add_all([standard_shipping, express_shipping])
```

- [ ] **Step 10: Write tests**

Create `/Users/huijokim/personal/openmarket/backend/tests/test_tax_shipping.py`:

```python
import pytest
from app.models.tax_shipping import TaxRate, ShippingMethod
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


@pytest.mark.asyncio
async def test_create_and_list_tax_rates(client, db):
    resp = await client.post("/api/tax-rates", json={"name": "VAT", "rate": "0.10", "region": "EU", "is_default": True})
    assert resp.status_code == 201
    resp = await client.get("/api/tax-rates")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "VAT"


@pytest.mark.asyncio
async def test_create_and_list_shipping_methods(client, db):
    resp = await client.post("/api/shipping-methods", json={"name": "Standard", "price": "5.00"})
    assert resp.status_code == 201
    resp = await client.get("/api/shipping-methods")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_order_includes_tax(client, db):
    tax = TaxRate(name="Tax", rate=0.10, is_default=True)
    db.add(tax)
    location = Location(name="Store", address="1 Main")
    db.add(location)
    await db.flush()
    product = Product(title="Item", handle="item-tax", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="Std", price=100.00)
    db.add(variant)
    await db.flush()
    inv = InventoryItem(variant_id=variant.id)
    db.add(inv)
    await db.flush()
    level = InventoryLevel(inventory_item_id=inv.id, location_id=location.id, available=50)
    db.add(level)
    await db.commit()

    resp = await client.post("/api/orders", json={
        "source": "web",
        "line_items": [{"variant_id": variant.id, "quantity": 1}],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert float(data["subtotal"]) == 100.0
    assert float(data["tax_amount"]) == 10.0
    assert float(data["total_price"]) == 110.0
```

- [ ] **Step 11: Run tests**

```bash
cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_tax_shipping.py tests/test_orders.py -v
```

Expected: All pass. Existing order tests still pass (they have no default tax rate, so tax_amount=0).

- [ ] **Step 12: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add backend/app/models/tax_shipping.py backend/app/models/__init__.py backend/app/models/order.py backend/app/schemas/order.py backend/app/schemas/tax_shipping.py backend/app/api/tax_shipping.py backend/app/main.py backend/app/services/order.py backend/app/api/orders.py backend/seed.py backend/tests/test_tax_shipping.py
git commit -m "feat: add tax rates, shipping methods, and include in order calculation"
```

---

## Task 6: Tax and Shipping in Store Checkout UI

**Files:**
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/api.ts`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/types.ts`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/CartCheckoutPage.tsx`

### Context

The store checkout currently shows just the cart total and a COD payment notice. We need to show shipping method selection, tax calculation, and a full order summary breakdown.

### Steps

- [ ] **Step 1: Add frontend types and API methods**

In `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/types.ts`, add:

```typescript
export interface TaxRate {
  id: number;
  name: string;
  rate: string;
  region: string;
  is_default: boolean;
}

export interface ShippingMethod {
  id: number;
  name: string;
  price: string;
  min_order_amount: string;
  is_active: boolean;
}
```

In `/Users/huijokim/personal/openmarket/frontend/packages/shared/src/api.ts`, add:

```typescript
taxRates: {
  list: () => request<import("./types").TaxRate[]>("/tax-rates"),
},
shippingMethods: {
  list: () => request<import("./types").ShippingMethod[]>("/shipping-methods"),
},
```

- [ ] **Step 2: Update CartCheckoutPage with shipping and tax**

In `/Users/huijokim/personal/openmarket/frontend/packages/store/src/pages/CartCheckoutPage.tsx`:

Add imports for the new types:
```typescript
import type { ShippingMethod, TaxRate } from "@openmarket/shared";
```

Add state variables after the existing state declarations:
```typescript
const [shippingMethods, setShippingMethods] = useState<ShippingMethod[]>([]);
const [selectedShipping, setSelectedShipping] = useState<number | null>(null);
const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
```

Add an effect to load shipping methods and tax rates:
```typescript
useEffect(() => {
  api.shippingMethods.list().then((methods) => {
    setShippingMethods(methods);
    if (methods.length > 0) setSelectedShipping(methods[0].id);
  });
  api.taxRates.list().then(setTaxRates);
}, []);
```

Compute tax and shipping amounts (replace the existing `finalTotal` computation):
```typescript
const defaultTax = taxRates.find((t) => t.is_default);
const taxRate = defaultTax ? parseFloat(defaultTax.rate) : 0;

const subtotalAfterDiscount = discount
  ? discount.type === "percentage" ? total * (1 - discount.value / 100) : Math.max(0, total - discount.value)
  : total;

const taxAmount = subtotalAfterDiscount * taxRate;

const selectedMethod = shippingMethods.find((m) => m.id === selectedShipping);
const shippingCost = selectedMethod
  ? (parseFloat(selectedMethod.min_order_amount) > 0 && subtotalAfterDiscount >= parseFloat(selectedMethod.min_order_amount))
    ? 0
    : parseFloat(selectedMethod.price)
  : 0;

const finalTotal = subtotalAfterDiscount + taxAmount + shippingCost;
```

Add a shipping method selector section after the discount section and before the delivery details form:
```tsx
<div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
  <h3 style={{ margin: "0 0 12px", fontSize: "16px" }}>Shipping Method</h3>
  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
    {shippingMethods.map((m) => {
      const isFree = parseFloat(m.min_order_amount) > 0 && subtotalAfterDiscount >= parseFloat(m.min_order_amount);
      return (
        <label key={m.id} style={{
          display: "flex", alignItems: "center", gap: "10px", padding: "10px 12px",
          background: selectedShipping === m.id ? colors.brandLight : colors.surfaceMuted,
          border: `1px solid ${selectedShipping === m.id ? colors.brand : colors.border}`,
          borderRadius: radius.sm, cursor: "pointer",
        }}>
          <input type="radio" name="shipping" checked={selectedShipping === m.id}
            onChange={() => setSelectedShipping(m.id)} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 500, fontSize: "14px" }}>{m.name}</div>
            {parseFloat(m.min_order_amount) > 0 && (
              <div style={{ fontSize: "12px", color: colors.textSecondary }}>
                Free on orders over ${m.min_order_amount}
              </div>
            )}
          </div>
          <div style={{ fontWeight: 600, color: isFree ? colors.success : colors.textPrimary }}>
            {isFree ? "FREE" : `$${parseFloat(m.price).toFixed(2)}`}
          </div>
        </label>
      );
    })}
  </div>
</div>
```

Replace the existing total display with a breakdown:
```tsx
<div style={{ fontSize: "14px", marginTop: spacing.md }}>
  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
    <span style={{ color: colors.textSecondary }}>Subtotal</span>
    <span>${subtotalAfterDiscount.toFixed(2)}</span>
  </div>
  {taxRate > 0 && (
    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
      <span style={{ color: colors.textSecondary }}>Tax ({(taxRate * 100).toFixed(0)}%)</span>
      <span>${taxAmount.toFixed(2)}</span>
    </div>
  )}
  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
    <span style={{ color: colors.textSecondary }}>Shipping</span>
    <span>{shippingCost === 0 ? "FREE" : `$${shippingCost.toFixed(2)}`}</span>
  </div>
  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "20px", fontWeight: 700, borderTop: `1px solid ${colors.border}`, paddingTop: "8px" }}>
    <span>Total</span>
    <span>${finalTotal.toFixed(2)}</span>
  </div>
</div>
```

Update `placeOrder` to pass `shipping_method_id`:
```typescript
const order = await api.orders.create({
  source: "web", customer_name: name, customer_phone: phone,
  shipping_address: { address1: address, city, zip },
  shipping_method_id: selectedShipping,
  line_items: items.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
});
```

- [ ] **Step 3: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add frontend/packages/shared/src/types.ts frontend/packages/shared/src/api.ts frontend/packages/store/src/pages/CartCheckoutPage.tsx
git commit -m "feat: add tax and shipping display to store checkout"
```

---

## Task 7: POS Receipt Printing

**Files:**
- Create: `/Users/huijokim/personal/openmarket/frontend/packages/pos/src/components/Receipt.tsx`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/pos/src/pages/SalePage.tsx`

### Context

The POS completes sales but has no receipt. After `completeSale`, it shows a green success message for 3 seconds, then resets. We'll add a receipt modal with a print button that uses the browser's `window.print()`.

### Steps

- [ ] **Step 1: Create Receipt component**

Create `/Users/huijokim/personal/openmarket/frontend/packages/pos/src/components/Receipt.tsx`:

```tsx
import { Button, colors, spacing, radius } from "@openmarket/shared";

interface ReceiptItem {
  productTitle: string;
  variantTitle: string;
  quantity: number;
  price: string;
}

interface ReceiptProps {
  orderNumber: string;
  items: ReceiptItem[];
  total: number;
  onClose: () => void;
}

export function Receipt({ orderNumber, items, total, onClose }: ReceiptProps) {
  const handlePrint = () => {
    window.print();
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex",
      alignItems: "center", justifyContent: "center", zIndex: 1000,
    }}>
      <div style={{
        background: "#fff", borderRadius: radius.md, width: 360, maxHeight: "90vh",
        overflow: "auto", padding: spacing.lg,
      }}>
        {/* Receipt content - this is what gets printed */}
        <div id="receipt-content">
          <div style={{ textAlign: "center", marginBottom: spacing.md }}>
            <h2 style={{ margin: "0 0 4px", fontSize: "18px" }}>OpenMarket</h2>
            <p style={{ margin: 0, fontSize: "12px", color: colors.textSecondary }}>Receipt</p>
          </div>

          <div style={{ borderBottom: `1px dashed ${colors.border}`, marginBottom: spacing.sm, paddingBottom: spacing.sm }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", color: colors.textSecondary }}>
              <span>Order: {orderNumber}</span>
              <span>{new Date().toLocaleString()}</span>
            </div>
          </div>

          <div style={{ marginBottom: spacing.sm }}>
            {items.map((item, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: "space-between", padding: "4px 0",
                fontSize: "14px", borderBottom: i < items.length - 1 ? `1px solid ${colors.border}` : undefined,
              }}>
                <div>
                  <div style={{ fontWeight: 500 }}>{item.productTitle}</div>
                  <div style={{ fontSize: "12px", color: colors.textSecondary }}>
                    {item.variantTitle} x {item.quantity}
                  </div>
                </div>
                <div style={{ fontWeight: 500 }}>
                  ${(parseFloat(item.price) * item.quantity).toFixed(2)}
                </div>
              </div>
            ))}
          </div>

          <div style={{
            borderTop: `2px solid ${colors.textPrimary}`, paddingTop: spacing.sm,
            display: "flex", justifyContent: "space-between", fontSize: "18px", fontWeight: 700,
          }}>
            <span>Total</span>
            <span>${total.toFixed(2)}</span>
          </div>

          <div style={{ textAlign: "center", marginTop: spacing.md, fontSize: "12px", color: colors.textSecondary }}>
            Thank you for your purchase!
          </div>
        </div>

        {/* Action buttons - hidden when printing */}
        <div className="no-print" style={{ display: "flex", gap: "8px", marginTop: spacing.lg }}>
          <Button variant="primary" fullWidth onClick={handlePrint}>Print Receipt</Button>
          <Button variant="secondary" fullWidth onClick={onClose}>Close</Button>
        </div>
      </div>

      {/* Print styles */}
      <style>{`
        @media print {
          body > *:not([style*="position: fixed"]) { display: none !important; }
          .no-print { display: none !important; }
        }
      `}</style>
    </div>
  );
}
```

- [ ] **Step 2: Integrate Receipt into SalePage**

In `/Users/huijokim/personal/openmarket/frontend/packages/pos/src/pages/SalePage.tsx`:

Add import:
```typescript
import { Receipt } from "../components/Receipt";
```

Add state for receipt:
```typescript
const [receiptData, setReceiptData] = useState<{
  orderNumber: string;
  items: { productTitle: string; variantTitle: string; quantity: number; price: string }[];
  total: number;
} | null>(null);
```

Modify `completeSale` to show receipt instead of success message:
```typescript
const completeSale = async () => {
  setError("");
  try {
    const order = await api.orders.create({
      source: "pos",
      line_items: saleItems.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
    });
    setReceiptData({
      orderNumber: order.order_number,
      items: saleItems.map((i) => ({
        productTitle: i.productTitle,
        variantTitle: i.variant.title,
        quantity: i.quantity,
        price: i.variant.price,
      })),
      total,
    });
    setSaleItems([]);
  } catch (e: any) { setError(e.message); }
};
```

Add the receipt modal at the end of the component's return, before the closing `</div>`:
```tsx
{receiptData && (
  <Receipt
    orderNumber={receiptData.orderNumber}
    items={receiptData.items}
    total={receiptData.total}
    onClose={() => { setReceiptData(null); barcodeRef.current?.focus(); }}
  />
)}
```

Remove or keep the existing `success` state/display as a fallback — if receipt is shown, the success banner is no longer needed. Simplest: remove the `success` state and its `useEffect`, and the success banner in the JSX.

- [ ] **Step 3: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add frontend/packages/pos/src/components/Receipt.tsx frontend/packages/pos/src/pages/SalePage.tsx
git commit -m "feat: add receipt modal with print support to POS"
```

---

## Task 8: POS Returns/Refunds

**Files:**
- Create: `/Users/huijokim/personal/openmarket/backend/app/api/returns.py`
- Create: `/Users/huijokim/personal/openmarket/backend/app/schemas/returns.py`
- Create: `/Users/huijokim/personal/openmarket/backend/app/services/returns.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/main.py`
- Create: `/Users/huijokim/personal/openmarket/frontend/packages/pos/src/components/ReturnModal.tsx`
- Modify: `/Users/huijokim/personal/openmarket/frontend/packages/pos/src/pages/SalePage.tsx`
- Create: `/Users/huijokim/personal/openmarket/backend/tests/test_returns.py`

### Context

There's no return/refund capability. POS operators need to look up an order and return items, restoring inventory. We'll create a simple return system: look up an order by number, select items to return, create a return record, and restore inventory.

### Steps

- [ ] **Step 1: Create return model (add to order.py)**

In `/Users/huijokim/personal/openmarket/backend/app/models/order.py`, add:

```python
class Return(Base):
    __tablename__ = "returns"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    reason = Column(String, default="")
    total_refund = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order")
    items = relationship("ReturnItem", back_populates="return_record", cascade="all, delete-orphan")


class ReturnItem(Base):
    __tablename__ = "return_items"

    id = Column(Integer, primary_key=True)
    return_id = Column(Integer, ForeignKey("returns.id", ondelete="CASCADE"), nullable=False)
    line_item_id = Column(Integer, ForeignKey("line_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)

    return_record = relationship("Return", back_populates="items")
    line_item = relationship("LineItem")
```

- [ ] **Step 2: Create return schemas**

Create `/Users/huijokim/personal/openmarket/backend/app/schemas/returns.py`:

```python
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class ReturnItemCreate(BaseModel):
    line_item_id: int
    quantity: int


class ReturnCreate(BaseModel):
    order_id: int
    reason: str = ""
    items: list[ReturnItemCreate]


class ReturnItemOut(BaseModel):
    id: int
    line_item_id: int
    quantity: int

    model_config = {"from_attributes": True}


class ReturnOut(BaseModel):
    id: int
    order_id: int
    reason: str
    total_refund: Decimal
    created_at: datetime
    items: list[ReturnItemOut] = []

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create return service**

Create `/Users/huijokim/personal/openmarket/backend/app/services/returns.py`:

```python
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import InventoryItem
from app.models.order import LineItem, Order, Return, ReturnItem
from app.ws.manager import manager


async def create_return(
    db: AsyncSession,
    order_id: int,
    return_items: list[dict],
    reason: str = "",
) -> Return:
    # Verify order exists
    order_result = await db.execute(
        select(Order).where(Order.id == order_id).options(selectinload(Order.line_items))
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise ValueError("Order not found")

    total_refund = Decimal("0")
    items = []

    for item_data in return_items:
        # Get line item
        li_result = await db.execute(
            select(LineItem).where(LineItem.id == item_data["line_item_id"])
        )
        li = li_result.scalar_one_or_none()
        if not li or li.order_id != order_id:
            raise ValueError(f"Line item {item_data['line_item_id']} not found in order")

        qty = item_data["quantity"]
        if qty > li.quantity:
            raise ValueError(f"Cannot return more than ordered ({li.quantity})")

        total_refund += li.price * qty

        items.append(ReturnItem(line_item_id=li.id, quantity=qty))

        # Restore inventory
        inv_result = await db.execute(
            select(InventoryItem).where(InventoryItem.variant_id == li.variant_id)
        )
        inv_item = inv_result.scalar_one_or_none()
        if inv_item:
            result = await db.execute(
                text("""
                    UPDATE inventory_levels
                    SET available = available + :qty
                    WHERE inventory_item_id = :inv_id
                    RETURNING id, available, location_id
                """),
                {"qty": qty, "inv_id": inv_item.id},
            )
            row = result.fetchone()
            if row:
                await manager.broadcast({
                    "type": "inventory_updated",
                    "inventory_item_id": inv_item.id,
                    "location_id": row.location_id,
                    "available": row.available,
                })

    return_record = Return(
        order_id=order_id,
        reason=reason,
        total_refund=total_refund,
    )
    for item in items:
        return_record.items.append(item)

    db.add(return_record)
    await db.commit()
    await db.refresh(return_record, ["items"])
    return return_record
```

- [ ] **Step 4: Create return API**

Create `/Users/huijokim/personal/openmarket/backend/app/api/returns.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.order import Return
from app.schemas.returns import ReturnCreate, ReturnOut
from app.services.returns import create_return

router = APIRouter(prefix="/api", tags=["returns"])


@router.post("/returns", response_model=ReturnOut, status_code=201)
async def create(body: ReturnCreate, db: AsyncSession = Depends(get_db)):
    try:
        return_record = await create_return(
            db=db,
            order_id=body.order_id,
            return_items=[item.model_dump() for item in body.items],
            reason=body.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return return_record


@router.get("/orders/{order_id}/returns", response_model=list[ReturnOut])
async def list_returns(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Return)
        .where(Return.order_id == order_id)
        .options(selectinload(Return.items))
    )
    return result.scalars().all()
```

- [ ] **Step 5: Register returns router**

In `/Users/huijokim/personal/openmarket/backend/app/main.py`:

```python
from app.api.returns import router as returns_router
app.include_router(returns_router)
```

- [ ] **Step 6: Write return tests**

Create `/Users/huijokim/personal/openmarket/backend/tests/test_returns.py`:

```python
import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_and_create_order(client, db):
    location = Location(name="Store", address="1 Main")
    db.add(location)
    await db.flush()
    product = Product(title="Soda", handle="soda-ret", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="500ml", price=2.50)
    db.add(variant)
    await db.flush()
    inv = InventoryItem(variant_id=variant.id)
    db.add(inv)
    await db.flush()
    level = InventoryLevel(inventory_item_id=inv.id, location_id=location.id, available=50)
    db.add(level)
    await db.commit()

    resp = await client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": variant.id, "quantity": 3}],
    })
    order = resp.json()
    return {
        "order_id": order["id"],
        "line_item_id": order["line_items"][0]["id"],
        "variant_id": variant.id,
        "location_id": location.id,
        "inv_item_id": inv.id,
    }


@pytest.mark.asyncio
async def test_create_return(client, db):
    ids = await seed_and_create_order(client, db)
    resp = await client.post("/api/returns", json={
        "order_id": ids["order_id"],
        "reason": "Defective",
        "items": [{"line_item_id": ids["line_item_id"], "quantity": 1}],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert float(data["total_refund"]) == 2.50
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_return_restores_inventory(client, db):
    ids = await seed_and_create_order(client, db)
    # After order: 50 - 3 = 47
    await client.post("/api/returns", json={
        "order_id": ids["order_id"],
        "items": [{"line_item_id": ids["line_item_id"], "quantity": 2}],
    })
    inv = await client.get(f"/api/inventory-levels?location_id={ids['location_id']}")
    # After return: 47 + 2 = 49
    level = next(l for l in inv.json() if l["inventory_item_id"] == ids["inv_item_id"])
    assert level["available"] == 49


@pytest.mark.asyncio
async def test_return_over_quantity_fails(client, db):
    ids = await seed_and_create_order(client, db)
    resp = await client.post("/api/returns", json={
        "order_id": ids["order_id"],
        "items": [{"line_item_id": ids["line_item_id"], "quantity": 999}],
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_returns_for_order(client, db):
    ids = await seed_and_create_order(client, db)
    await client.post("/api/returns", json={
        "order_id": ids["order_id"],
        "items": [{"line_item_id": ids["line_item_id"], "quantity": 1}],
    })
    resp = await client.get(f"/api/orders/{ids['order_id']}/returns")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
```

- [ ] **Step 7: Run tests**

```bash
cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_returns.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 8: Create ReturnModal frontend component**

Create `/Users/huijokim/personal/openmarket/frontend/packages/pos/src/components/ReturnModal.tsx`:

```tsx
import { useState } from "react";
import { api, Button, Spinner, colors, spacing, radius, baseStyles } from "@openmarket/shared";
import type { Order } from "@openmarket/shared";

interface ReturnModalProps {
  onClose: () => void;
}

export function ReturnModal({ onClose }: ReturnModalProps) {
  const [orderNumber, setOrderNumber] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [returnQtys, setReturnQtys] = useState<Record<number, number>>({});
  const [reason, setReason] = useState("");

  const lookupOrder = async () => {
    if (!orderNumber.trim()) return;
    setLoading(true);
    setError("");
    try {
      const o = await api.orders.lookup(orderNumber.trim());
      setOrder(o);
      const qtys: Record<number, number> = {};
      o.line_items.forEach((li) => { qtys[li.id] = 0; });
      setReturnQtys(qtys);
    } catch {
      setError("Order not found.");
    } finally {
      setLoading(false);
    }
  };

  const processReturn = async () => {
    if (!order) return;
    const items = Object.entries(returnQtys)
      .filter(([, qty]) => qty > 0)
      .map(([id, qty]) => ({ line_item_id: parseInt(id), quantity: qty }));
    if (items.length === 0) { setError("Select at least one item to return."); return; }

    setLoading(true);
    setError("");
    try {
      const resp = await fetch("/api/returns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: order.id, reason, items }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: "Return failed" }));
        throw new Error(err.detail);
      }
      const data = await resp.json();
      setSuccess(`Return processed! Refund: $${parseFloat(data.total_refund).toFixed(2)}`);
      setOrder(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex",
      alignItems: "center", justifyContent: "center", zIndex: 1000,
    }}>
      <div style={{ background: "#fff", borderRadius: radius.md, width: 440, maxHeight: "90vh", overflow: "auto", padding: spacing.lg }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
          <h2 style={{ margin: 0, fontSize: "18px" }}>Process Return</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>&times;</Button>
        </div>

        {success ? (
          <div>
            <div style={{ background: colors.successSurface, color: colors.success, padding: "12px", borderRadius: radius.sm, fontSize: "16px", fontWeight: 600, marginBottom: spacing.md }}>
              {success}
            </div>
            <Button variant="primary" fullWidth onClick={onClose}>Done</Button>
          </div>
        ) : !order ? (
          <div>
            <div style={{ display: "flex", gap: "8px", marginBottom: spacing.sm }}>
              <input placeholder="Order number (e.g. ORD-...)" value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && lookupOrder()}
                style={baseStyles.input} />
              <Button variant="primary" onClick={lookupOrder} loading={loading} style={{ flexShrink: 0 }}>Look Up</Button>
            </div>
            {error && <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px" }}>{error}</div>}
          </div>
        ) : (
          <div>
            <div style={{ fontSize: "14px", color: colors.textSecondary, marginBottom: spacing.md }}>
              Order: <strong>{order.order_number}</strong> &middot; ${order.total_price}
            </div>

            <div style={{ marginBottom: spacing.md }}>
              {order.line_items.map((li) => (
                <div key={li.id} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "8px 0", borderBottom: `1px solid ${colors.border}`,
                }}>
                  <div>
                    <div style={{ fontWeight: 500, fontSize: "14px" }}>{li.title}</div>
                    <div style={{ fontSize: "13px", color: colors.textSecondary }}>
                      ${li.price} x {li.quantity} ordered
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span style={{ fontSize: "13px", color: colors.textSecondary }}>Return:</span>
                    <Button variant="secondary" size="sm"
                      onClick={() => setReturnQtys((p) => ({ ...p, [li.id]: Math.max(0, (p[li.id] || 0) - 1) }))}>-</Button>
                    <span style={{ width: 24, textAlign: "center", fontWeight: 600 }}>{returnQtys[li.id] || 0}</span>
                    <Button variant="secondary" size="sm"
                      onClick={() => setReturnQtys((p) => ({ ...p, [li.id]: Math.min(li.quantity, (p[li.id] || 0) + 1) }))}>+</Button>
                  </div>
                </div>
              ))}
            </div>

            <input placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} style={{ ...baseStyles.input, marginBottom: spacing.md }} />

            {error && <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px", marginBottom: spacing.sm }}>{error}</div>}

            <div style={{ display: "flex", gap: "8px" }}>
              <Button variant="secondary" fullWidth onClick={() => setOrder(null)}>Back</Button>
              <Button variant="danger" fullWidth onClick={processReturn} loading={loading}>Process Return</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 9: Add Return button to POS SalePage**

In `/Users/huijokim/personal/openmarket/frontend/packages/pos/src/pages/SalePage.tsx`:

Add import:
```typescript
import { ReturnModal } from "../components/ReturnModal";
```

Add state:
```typescript
const [showReturn, setShowReturn] = useState(false);
```

Add a "Returns" button in the POS header area (next to the "POS" heading):
```tsx
<div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: `0 0 ${spacing.lg}` }}>
  <h2 style={{ margin: 0, color: colors.brand }}>POS</h2>
  <Button variant="secondary" size="sm" onClick={() => setShowReturn(true)}>Returns</Button>
</div>
```

Add the modal at the end of the return JSX:
```tsx
{showReturn && <ReturnModal onClose={() => setShowReturn(false)} />}
```

- [ ] **Step 10: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add backend/app/models/order.py backend/app/schemas/returns.py backend/app/services/returns.py backend/app/api/returns.py backend/app/main.py backend/tests/test_returns.py frontend/packages/pos/src/components/ReturnModal.tsx frontend/packages/pos/src/pages/SalePage.tsx
git commit -m "feat: add POS receipt printing and returns with inventory restoration"
```

---

## Task 9: Database Indexes

**Files:**
- Modify: `/Users/huijokim/personal/openmarket/backend/app/models/product.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/models/order.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/models/customer.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/app/models/inventory.py`

### Context

No database indexes exist beyond primary keys and unique constraints. Queries on `barcode`, `order_number`, `customer.email`, `customer.phone`, and foreign keys need indexes for performance.

### Steps

- [ ] **Step 1: Add indexes to Product models**

In `/Users/huijokim/personal/openmarket/backend/app/models/product.py`:

Add `Index` import:
```python
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
```

Add to `Product` class:
```python
__table_args__ = (
    Index("ix_products_product_type", "product_type"),
    Index("ix_products_status", "status"),
)
```

Add to `ProductVariant` class:
```python
__table_args__ = (
    Index("ix_product_variants_barcode", "barcode"),
    Index("ix_product_variants_sku", "sku"),
    Index("ix_product_variants_product_id", "product_id"),
)
```

Add to `ProductImage` class:
```python
__table_args__ = (
    Index("ix_product_images_product_id", "product_id"),
)
```

- [ ] **Step 2: Add indexes to Order models**

In `/Users/huijokim/personal/openmarket/backend/app/models/order.py`:

Add `Index` import:
```python
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, func
```

Add to `Order` class:
```python
__table_args__ = (
    Index("ix_orders_customer_id", "customer_id"),
    Index("ix_orders_source", "source"),
    Index("ix_orders_fulfillment_status", "fulfillment_status"),
    Index("ix_orders_created_at", "created_at"),
)
```

Add to `LineItem` class:
```python
__table_args__ = (
    Index("ix_line_items_order_id", "order_id"),
    Index("ix_line_items_variant_id", "variant_id"),
)
```

- [ ] **Step 3: Add indexes to Customer model**

In `/Users/huijokim/personal/openmarket/backend/app/models/customer.py`:

Add `Index` import and add to `Customer` class:
```python
__table_args__ = (
    Index("ix_customers_email", "email"),
    Index("ix_customers_phone", "phone"),
)
```

- [ ] **Step 4: Add indexes to Inventory model**

In `/Users/huijokim/personal/openmarket/backend/app/models/inventory.py`:

Add `Index` import and add to `InventoryLevel` class:
```python
__table_args__ = (
    Index("ix_inventory_levels_inventory_item_id", "inventory_item_id"),
    Index("ix_inventory_levels_location_id", "location_id"),
)
```

- [ ] **Step 5: Run existing tests to verify no regressions**

```bash
cd /Users/huijokim/personal/openmarket/backend && python -m pytest -v
```

Expected: All existing tests pass. The indexes are created by `Base.metadata.create_all` in the test setup.

- [ ] **Step 6: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add backend/app/models/product.py backend/app/models/order.py backend/app/models/customer.py backend/app/models/inventory.py
git commit -m "feat: add database indexes for query performance"
```

---

## Task 10: CI/CD with GitHub Actions

**Files:**
- Create: `/Users/huijokim/personal/openmarket/.github/workflows/test.yml`

### Context

There's no CI/CD. Tests run locally against a PostgreSQL test DB on port 5433. We need a GitHub Actions workflow that runs tests on push/PR.

### Steps

- [ ] **Step 1: Create GitHub Actions workflow**

Create `/Users/huijokim/personal/openmarket/.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: openmarket_test
          POSTGRES_USER: openmarket
          POSTGRES_PASSWORD: openmarket
        ports:
          - 5433:5432
        options: >-
          --health-cmd "pg_isready -U openmarket"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        working-directory: backend
        run: pip install -r requirements.txt

      - name: Run tests
        working-directory: backend
        run: python -m pytest -v --tb=short

  frontend-build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install pnpm
        run: npm install -g pnpm

      - name: Install dependencies
        working-directory: frontend
        run: pnpm install --frozen-lockfile

      - name: Build all packages
        working-directory: frontend
        run: pnpm build
```

- [ ] **Step 2: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add .github/workflows/test.yml
git commit -m "ci: add GitHub Actions workflow for backend tests and frontend build"
```

---

## Task 11: Structured Logging

**Files:**
- Modify: `/Users/huijokim/personal/openmarket/backend/app/main.py`
- Modify: `/Users/huijokim/personal/openmarket/backend/requirements.txt`

### Context

The backend has no logging. We need structured JSON logging for API requests and key events.

### Steps

- [ ] **Step 1: Add logging middleware**

In `/Users/huijokim/personal/openmarket/backend/app/main.py`, add logging setup and middleware:

```python
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("openmarket")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = round((time.time() - start) * 1000, 1)
        logger.info(
            "%s %s %s %sms",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        return response
```

Add the middleware after the CORS middleware:
```python
app.add_middleware(LoggingMiddleware)
```

- [ ] **Step 2: Run tests to verify no breakage**

```bash
cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_health.py -v
```

Expected: Pass.

- [ ] **Step 3: Commit**

```bash
cd /Users/huijokim/personal/openmarket
git add backend/app/main.py
git commit -m "feat: add structured request logging middleware"
```
