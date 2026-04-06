# High-Priority UX Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the highest-impact UX gaps across customer store, admin dashboard, and POS for both customers and admins.

**Architecture:** Shared infrastructure (toast, confirm dialog, debounce, localStorage cart) is built first in `@openmarket/shared`, then consumed by store/admin/POS. Backend API improvements (pagination, search, discount CRUD, locations) come next, followed by frontend pages that depend on them. Each phase produces independently shippable work.

**Tech Stack:** React 18, TypeScript, FastAPI, SQLAlchemy async, PostgreSQL, Pydantic v2, pytest-asyncio, pnpm monorepo, Vite

---

## File Structure Overview

### New Files
- `frontend/packages/shared/src/components/Toast.tsx` - Toast notification system with context provider
- `frontend/packages/shared/src/components/ConfirmDialog.tsx` - Modal confirmation dialog
- `frontend/packages/shared/src/useDebounce.ts` - Debounce hook for search inputs
- `frontend/packages/shared/src/exportCsv.ts` - CSV export utility
- `frontend/packages/admin/src/pages/CustomersPage.tsx` - Admin customer management
- `frontend/packages/admin/src/pages/SettingsPage.tsx` - Admin settings (tax, shipping, discounts, locations)
- `backend/app/schemas/location.py` - Location Pydantic schemas
- `backend/tests/test_pagination.py` - Tests for pagination
- `backend/tests/test_discount_crud.py` - Tests for discount CRUD
- `backend/tests/test_order_search.py` - Tests for order search

### Modified Files
- `frontend/packages/shared/src/index.ts` - Export new components/hooks
- `frontend/packages/shared/src/api.ts` - Add pagination params, discount CRUD, locations API, order search
- `frontend/packages/shared/src/types.ts` - Add PaginatedResponse, Location, DiscountCreate types
- `frontend/packages/store/src/store/cartStore.tsx` - localStorage persistence
- `frontend/packages/store/src/pages/ShopPage.tsx` - Debounced search, product sorting
- `frontend/packages/store/src/pages/CartCheckoutPage.tsx` - Form validation, remove confirmation
- `frontend/packages/admin/src/App.tsx` - Add Customers and Settings nav links, wrap with ToastProvider
- `frontend/packages/admin/src/pages/ProductsInventoryPage.tsx` - Toast, confirm dialogs, location selector
- `frontend/packages/admin/src/pages/OrdersPage.tsx` - Search, filter, export
- `frontend/packages/admin/src/pages/AnalyticsPage.tsx` - Export button
- `frontend/packages/store/src/App.tsx` - Wrap with ToastProvider
- `frontend/packages/pos/src/App.tsx` - Add header, wrap with ToastProvider
- `frontend/packages/pos/src/pages/SalePage.tsx` - Keyboard shortcuts, toast, receipt reprint
- `backend/app/api/products.py` - Add pagination, sort_by params
- `backend/app/api/orders.py` - Add search, date_from/date_to, pagination
- `backend/app/api/customers.py` - Add search, pagination
- `backend/app/api/discounts.py` - Add CRUD endpoints
- `backend/app/api/inventory.py` - Add location list endpoint
- `backend/app/schemas/discount.py` - Add DiscountCreate, DiscountUpdate schemas
- `backend/app/models/__init__.py` - Export Return, ReturnItem (already exists but verify)

---

## Phase 1: Shared Infrastructure

### Task 1: Toast Notification Component

**Files:**
- Create: `frontend/packages/shared/src/components/Toast.tsx`
- Modify: `frontend/packages/shared/src/index.ts`

- [ ] **Step 1: Create Toast component with context provider**

```tsx
// frontend/packages/shared/src/components/Toast.tsx
import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { colors, radius, spacing, shadow, font } from "../tokens";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: ToastType = "success") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      <div style={{ position: "fixed", bottom: spacing.lg, right: spacing.lg, zIndex: 9999, display: "flex", flexDirection: "column", gap: spacing.sm }}>
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDone={() => removeToast(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 3000);
    return () => clearTimeout(timer);
  }, [onDone]);

  const bg = toast.type === "success" ? colors.successSurface
    : toast.type === "error" ? colors.dangerSurface
    : colors.surface;
  const fg = toast.type === "success" ? colors.success
    : toast.type === "error" ? colors.danger
    : colors.textPrimary;

  return (
    <div style={{
      background: bg, color: fg, border: `1px solid ${fg}`,
      padding: "10px 16px", borderRadius: radius.sm,
      fontSize: "14px", fontFamily: font.body, fontWeight: 500,
      boxShadow: shadow.md, minWidth: 240, maxWidth: 400,
      cursor: "pointer",
    }} onClick={onDone}>
      {toast.message}
    </div>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
```

- [ ] **Step 2: Export from shared index**

Add to `frontend/packages/shared/src/index.ts`:
```ts
export { ToastProvider, useToast } from "./components/Toast";
```

- [ ] **Step 3: Verify build**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/shared run build`
Expected: Clean build with no type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/shared/src/components/Toast.tsx frontend/packages/shared/src/index.ts
git commit -m "feat: add Toast notification component with context provider"
```

---

### Task 2: Confirmation Dialog Component

**Files:**
- Create: `frontend/packages/shared/src/components/ConfirmDialog.tsx`
- Modify: `frontend/packages/shared/src/index.ts`

- [ ] **Step 1: Create ConfirmDialog component**

```tsx
// frontend/packages/shared/src/components/ConfirmDialog.tsx
import { colors, radius, spacing, shadow, font } from "../tokens";
import { Button } from "./Button";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title, message, confirmLabel = "Confirm", cancelLabel = "Cancel",
  variant = "primary", onConfirm, onCancel,
}: ConfirmDialogProps) {
  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 10000, fontFamily: font.body,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div style={{
        background: colors.surface, borderRadius: radius.md,
        padding: spacing.lg, width: 380, boxShadow: shadow.lg,
      }}>
        <h3 style={{ margin: "0 0 8px", fontSize: "16px" }}>{title}</h3>
        <p style={{ color: colors.textSecondary, fontSize: "14px", margin: "0 0 20px" }}>{message}</p>
        <div style={{ display: "flex", gap: spacing.sm, justifyContent: "flex-end" }}>
          <Button variant="ghost" onClick={onCancel}>{cancelLabel}</Button>
          <Button variant={variant} onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Export from shared index**

Add to `frontend/packages/shared/src/index.ts`:
```ts
export { ConfirmDialog } from "./components/ConfirmDialog";
```

- [ ] **Step 3: Verify build**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/shared run build`
Expected: Clean build with no type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/shared/src/components/ConfirmDialog.tsx frontend/packages/shared/src/index.ts
git commit -m "feat: add ConfirmDialog component for destructive action confirmation"
```

---

### Task 3: Cart Persistence with localStorage

**Files:**
- Modify: `frontend/packages/store/src/store/cartStore.tsx`

- [ ] **Step 1: Add localStorage read/write to cartStore**

Replace the full file `frontend/packages/store/src/store/cartStore.tsx`:

```tsx
import { createContext, useContext, useState, ReactNode, useCallback, useEffect } from "react";
import type { CartItem, Product, ProductVariant } from "@openmarket/shared";

const CART_KEY = "openmarket_cart";

function loadCart(): CartItem[] {
  try {
    const raw = localStorage.getItem(CART_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveCart(items: CartItem[]) {
  try {
    localStorage.setItem(CART_KEY, JSON.stringify(items));
  } catch { /* quota exceeded - silently ignore */ }
}

interface CartContextType {
  items: CartItem[];
  addItem: (product: Product, variant: ProductVariant) => void;
  removeItem: (variantId: number) => void;
  updateQuantity: (variantId: number, quantity: number) => void;
  clearCart: () => void;
  total: number;
}

const CartContext = createContext<CartContextType | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(loadCart);

  useEffect(() => { saveCart(items); }, [items]);

  const addItem = useCallback((product: Product, variant: ProductVariant) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.variant.id === variant.id);
      if (existing) {
        return prev.map((i) => i.variant.id === variant.id ? { ...i, quantity: i.quantity + 1 } : i);
      }
      return [...prev, { product, variant, quantity: 1 }];
    });
  }, []);

  const removeItem = useCallback((variantId: number) => {
    setItems((prev) => prev.filter((i) => i.variant.id !== variantId));
  }, []);

  const updateQuantity = useCallback((variantId: number, quantity: number) => {
    if (quantity <= 0) { setItems((prev) => prev.filter((i) => i.variant.id !== variantId)); return; }
    setItems((prev) => prev.map((i) => (i.variant.id === variantId ? { ...i, quantity } : i)));
  }, []);

  const clearCart = useCallback(() => setItems([]), []);

  const total = items.reduce((sum, item) => sum + parseFloat(item.variant.price) * item.quantity, 0);

  return (
    <CartContext.Provider value={{ items, addItem, removeItem, updateQuantity, clearCart, total }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}
```

- [ ] **Step 2: Verify the store app builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/store run build`
Expected: Clean build

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/store/src/store/cartStore.tsx
git commit -m "feat: persist cart to localStorage so it survives page refresh"
```

---

### Task 4: useDebounce Hook

**Files:**
- Create: `frontend/packages/shared/src/useDebounce.ts`
- Modify: `frontend/packages/shared/src/index.ts`

- [ ] **Step 1: Create useDebounce hook**

```ts
// frontend/packages/shared/src/useDebounce.ts
import { useState, useEffect } from "react";

export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
```

- [ ] **Step 2: Export from shared index**

Add to `frontend/packages/shared/src/index.ts`:
```ts
export { useDebounce } from "./useDebounce";
```

- [ ] **Step 3: Verify build**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/shared run build`
Expected: Clean build

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/shared/src/useDebounce.ts frontend/packages/shared/src/index.ts
git commit -m "feat: add useDebounce hook for search input throttling"
```

---

## Phase 2: Backend API Improvements

### Task 5: Pagination on Products, Orders, and Customers

**Files:**
- Modify: `backend/app/api/products.py`
- Modify: `backend/app/api/orders.py`
- Modify: `backend/app/api/customers.py`
- Test: `backend/tests/test_pagination.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_pagination.py
import pytest


@pytest.mark.asyncio
async def test_products_pagination(client):
    for i in range(5):
        await client.post("/api/products", json={
            "title": f"Product {i}", "handle": f"product-{i}",
            "variants": [{"price": "1.00"}],
        })
    # Default: no limit, returns all
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    assert len(resp.json()) == 5

    # With limit and offset
    resp = await client.get("/api/products?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await client.get("/api/products?limit=2&offset=3")
    assert resp.status_code == 200
    assert len(resp.json()) == 2  # items 3 and 4

    resp = await client.get("/api/products?limit=2&offset=5")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_orders_pagination(client):
    # Create a product with inventory first
    prod = await client.post("/api/products", json={
        "title": "Item", "handle": "item",
        "variants": [{"price": "5.00"}],
    })
    vid = prod.json()["variants"][0]["id"]
    # Set inventory
    await client.post("/api/inventory-levels/set", json={
        "inventory_item_id": vid, "location_id": 1, "available": 100,
    })
    for _ in range(3):
        await client.post("/api/orders", json={
            "source": "web",
            "line_items": [{"variant_id": vid, "quantity": 1}],
        })
    resp = await client.get("/api/orders?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_customers_pagination(client):
    for i in range(4):
        await client.post("/api/customers", json={
            "first_name": f"User{i}", "last_name": "Test", "phone": f"555-000{i}",
        })
    resp = await client.get("/api/customers?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_pagination.py -v`
Expected: FAIL because `limit` and `offset` query params are not accepted yet

- [ ] **Step 3: Add pagination params to products endpoint**

In `backend/app/api/products.py`, modify the `list_products` function signature and query:

```python
@router.get("/products", response_model=list[ProductListWithPriceOut])
async def list_products(
    status: str | None = None,
    search: str | None = None,
    product_type: str | None = None,
    sort_by: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Product.id, Product.title, Product.handle, Product.product_type,
            Product.status, Product.tags,
            sqlfunc.min(ProductVariant.price).label("min_price"),
        )
        .outerjoin(ProductVariant, ProductVariant.product_id == Product.id)
        .group_by(Product.id)
    )
    if status:
        query = query.where(Product.status == status)
    if search:
        query = query.where(Product.title.ilike(f"%{search}%"))
    if product_type:
        query = query.where(Product.product_type == product_type)

    if sort_by == "title":
        query = query.order_by(Product.title)
    elif sort_by == "price_asc":
        query = query.order_by(sqlfunc.min(ProductVariant.price).asc())
    elif sort_by == "price_desc":
        query = query.order_by(sqlfunc.min(ProductVariant.price).desc())
    elif sort_by == "newest":
        query = query.order_by(Product.id.desc())
    else:
        query = query.order_by(Product.id)

    query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await db.execute(query)
    rows = result.all()

    # Load first image for each product
    product_ids = [r.id for r in rows]
    image_map: dict[int, str | None] = {}
    if product_ids:
        img_result = await db.execute(
            select(ProductImage.product_id, ProductImage.src)
            .where(ProductImage.product_id.in_(product_ids))
            .order_by(ProductImage.product_id, ProductImage.position)
        )
        for img_row in img_result.all():
            if img_row.product_id not in image_map:
                image_map[img_row.product_id] = img_row.src

    return [
        ProductListWithPriceOut(
            id=r.id, title=r.title, handle=r.handle,
            product_type=r.product_type, status=r.status,
            tags=r.tags, min_price=r.min_price,
            image_url=image_map.get(r.id),
        )
        for r in rows
    ]
```

- [ ] **Step 4: Add pagination params to orders endpoint**

In `backend/app/api/orders.py`, modify `list_orders`:

```python
@router.get("/orders", response_model=list[OrderListOut])
async def list_orders(
    source: str | None = None,
    fulfillment_status: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Order)
    if source:
        query = query.where(Order.source == source)
    if fulfillment_status:
        query = query.where(Order.fulfillment_status == fulfillment_status)
    if search:
        query = query.where(Order.order_number.ilike(f"%{search}%"))
    if date_from:
        query = query.where(Order.created_at >= date_from)
    if date_to:
        query = query.where(Order.created_at <= date_to)
    query = query.order_by(Order.created_at.desc()).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
```

- [ ] **Step 5: Add pagination and search to customers endpoint**

In `backend/app/api/customers.py`, modify `list_customers`:

```python
@router.get("/customers", response_model=list[CustomerOut])
async def list_customers(
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Customer).options(selectinload(Customer.addresses))
    if search:
        pattern = f"%{search}%"
        query = query.where(
            (Customer.first_name.ilike(pattern))
            | (Customer.last_name.ilike(pattern))
            | (Customer.email.ilike(pattern))
            | (Customer.phone.ilike(pattern))
        )
    query = query.order_by(Customer.id).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_pagination.py -v`
Expected: All 3 tests PASS

- [ ] **Step 7: Run all existing tests to confirm no regressions**

Run: `cd /Users/huijokim/personal/openmarket/backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/products.py backend/app/api/orders.py backend/app/api/customers.py backend/tests/test_pagination.py
git commit -m "feat: add pagination, sorting, and search to products/orders/customers endpoints"
```

---

### Task 6: Discount CRUD Endpoints

**Files:**
- Modify: `backend/app/schemas/discount.py`
- Modify: `backend/app/api/discounts.py`
- Test: `backend/tests/test_discount_crud.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_discount_crud.py
import pytest
from datetime import datetime, timedelta, timezone


def _discount_payload(code="SAVE10"):
    now = datetime.now(timezone.utc)
    return {
        "code": code,
        "discount_type": "percentage",
        "value": "10.00",
        "starts_at": (now - timedelta(days=1)).isoformat(),
        "ends_at": (now + timedelta(days=30)).isoformat(),
    }


@pytest.mark.asyncio
async def test_create_discount(client):
    resp = await client.post("/api/discounts", json=_discount_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "SAVE10"
    assert data["discount_type"] == "percentage"


@pytest.mark.asyncio
async def test_list_discounts(client):
    await client.post("/api/discounts", json=_discount_payload("A"))
    await client.post("/api/discounts", json=_discount_payload("B"))
    resp = await client.get("/api/discounts")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_discount(client):
    create = await client.post("/api/discounts", json=_discount_payload())
    did = create.json()["id"]
    resp = await client.put(f"/api/discounts/{did}", json={"value": "20.00"})
    assert resp.status_code == 200
    assert resp.json()["value"] == "20.00"


@pytest.mark.asyncio
async def test_delete_discount(client):
    create = await client.post("/api/discounts", json=_discount_payload())
    did = create.json()["id"]
    resp = await client.delete(f"/api/discounts/{did}")
    assert resp.status_code == 200
    # Verify deleted
    resp = await client.get("/api/discounts")
    assert len(resp.json()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_discount_crud.py -v`
Expected: FAIL (endpoints don't exist)

- [ ] **Step 3: Add DiscountCreate and DiscountUpdate schemas**

Replace `backend/app/schemas/discount.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DiscountCreate(BaseModel):
    code: str
    discount_type: str
    value: Decimal
    starts_at: datetime
    ends_at: datetime


class DiscountUpdate(BaseModel):
    code: str | None = None
    discount_type: str | None = None
    value: Decimal | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class DiscountOut(BaseModel):
    id: int
    code: str
    discount_type: str
    value: Decimal
    starts_at: datetime
    ends_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Add CRUD endpoints to discounts router**

Replace `backend/app/api/discounts.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.discount import Discount
from app.schemas.discount import DiscountCreate, DiscountUpdate, DiscountOut

router = APIRouter(prefix="/api", tags=["discounts"])


@router.post("/discounts/lookup", response_model=DiscountOut)
async def lookup_discount(code: str, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Discount).where(
            Discount.code == code,
            Discount.starts_at <= now,
            Discount.ends_at >= now,
        )
    )
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found or expired")
    return discount


@router.get("/discounts", response_model=list[DiscountOut])
async def list_discounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Discount).order_by(Discount.id))
    return result.scalars().all()


@router.post("/discounts", response_model=DiscountOut, status_code=201)
async def create_discount(body: DiscountCreate, db: AsyncSession = Depends(get_db)):
    discount = Discount(**body.model_dump())
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return discount


@router.put("/discounts/{discount_id}", response_model=DiscountOut)
async def update_discount(discount_id: int, body: DiscountUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Discount).where(Discount.id == discount_id))
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(discount, key, value)
    await db.commit()
    await db.refresh(discount)
    return discount


@router.delete("/discounts/{discount_id}")
async def delete_discount(discount_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Discount).where(Discount.id == discount_id))
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    await db.delete(discount)
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/huijokim/personal/openmarket/backend && python -m pytest tests/test_discount_crud.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Run all tests to confirm no regressions**

Run: `cd /Users/huijokim/personal/openmarket/backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/discount.py backend/app/api/discounts.py backend/tests/test_discount_crud.py
git commit -m "feat: add discount CRUD endpoints for admin management"
```

---

### Task 7: Location List Endpoint

**Files:**
- Create: `backend/app/schemas/location.py`
- Modify: `backend/app/api/inventory.py`

- [ ] **Step 1: Create location schema**

```python
# backend/app/schemas/location.py
from pydantic import BaseModel


class LocationOut(BaseModel):
    id: int
    name: str
    address: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Add location list endpoint to inventory router**

Add at the top of routes in `backend/app/api/inventory.py` (after imports):

Add import:
```python
from app.models.inventory import InventoryLevel, Location
from app.schemas.location import LocationOut
```

Add endpoint (before existing endpoints):
```python
@router.get("/locations", response_model=list[LocationOut])
async def list_locations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Location).order_by(Location.id))
    return result.scalars().all()
```

- [ ] **Step 3: Run all tests**

Run: `cd /Users/huijokim/personal/openmarket/backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/location.py backend/app/api/inventory.py
git commit -m "feat: add location list endpoint for multi-location inventory UI"
```

---

## Phase 3: Frontend API Client & Types Update

### Task 8: Update API Client and Types for New Backend Features

**Files:**
- Modify: `frontend/packages/shared/src/types.ts`
- Modify: `frontend/packages/shared/src/api.ts`

- [ ] **Step 1: Add new types**

Add to the end of `frontend/packages/shared/src/types.ts`:

```ts
export interface Location {
  id: number;
  name: string;
  address: string;
}

export interface DiscountCreate {
  code: string;
  discount_type: string;
  value: string;
  starts_at: string;
  ends_at: string;
}
```

- [ ] **Step 2: Update API client with pagination, sorting, discount CRUD, locations, order search**

Replace `frontend/packages/shared/src/api.ts`:

```ts
const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function qs(params: Record<string, unknown>): string {
  const entries = Object.entries(params).filter(([, v]) => v != null && v !== "");
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

export const api = {
  products: {
    list: (params?: { status?: string; search?: string; product_type?: string; sort_by?: string; limit?: number; offset?: number }) =>
      request<import("./types").ProductListWithPrice[]>(`/products${qs(params ?? {})}`),
    get: (id: number) => request<import("./types").Product>(`/products/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Product>("/products", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Product>(`/products/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    archive: (id: number) =>
      request<import("./types").Product>(`/products/${id}`, { method: "DELETE" }),
  },
  variants: {
    lookup: (barcode: string) =>
      request<import("./types").VariantLookup>(`/variants/lookup?barcode=${encodeURIComponent(barcode)}`),
  },
  collections: {
    list: () => request<import("./types").Collection[]>("/collections"),
    products: (id: number) =>
      request<import("./types").ProductListWithPrice[]>(`/collections/${id}/products`),
  },
  inventory: {
    levels: (locationId: number) =>
      request<import("./types").InventoryLevel[]>(`/inventory-levels?location_id=${locationId}`),
    set: (data: { inventory_item_id: number; location_id: number; available: number }) =>
      request<import("./types").InventoryLevel>("/inventory-levels/set", { method: "POST", body: JSON.stringify(data) }),
    adjust: (data: { inventory_item_id: number; location_id: number; available_adjustment: number }) =>
      request<import("./types").InventoryLevel>("/inventory-levels/adjust", { method: "POST", body: JSON.stringify(data) }),
  },
  locations: {
    list: () => request<import("./types").Location[]>("/locations"),
  },
  orders: {
    list: (params?: { source?: string; fulfillment_status?: string; search?: string; date_from?: string; date_to?: string; limit?: number; offset?: number }) =>
      request<import("./types").OrderListItem[]>(`/orders${qs(params ?? {})}`),
    get: (id: number) => request<import("./types").Order>(`/orders/${id}`),
    lookup: (orderNumber: string) =>
      request<import("./types").Order>(`/orders/lookup?order_number=${encodeURIComponent(orderNumber)}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Order>("/orders", { method: "POST", body: JSON.stringify(data) }),
  },
  fulfillments: {
    create: (orderId: number, data: { status: string }) =>
      request<import("./types").Fulfillment>(`/orders/${orderId}/fulfillments`, { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: { status: string }) =>
      request<import("./types").Fulfillment>(`/fulfillments/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  },
  discounts: {
    lookup: (code: string) =>
      request<import("./types").Discount>(`/discounts/lookup?code=${encodeURIComponent(code)}`, { method: "POST" }),
    list: () => request<import("./types").Discount[]>("/discounts"),
    create: (data: import("./types").DiscountCreate) =>
      request<import("./types").Discount>("/discounts", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Discount>(`/discounts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: number) => request<{ ok: boolean }>(`/discounts/${id}`, { method: "DELETE" }),
  },
  analytics: {
    summary: (days?: number) =>
      request<import("./types").AnalyticsSummary>(`/analytics/summary${days ? `?days=${days}` : ""}`),
  },
  taxRates: {
    list: () => request<import("./types").TaxRate[]>("/tax-rates"),
    create: (data: Record<string, unknown>) =>
      request<import("./types").TaxRate>("/tax-rates", { method: "POST", body: JSON.stringify(data) }),
  },
  shippingMethods: {
    list: () => request<import("./types").ShippingMethod[]>("/shipping-methods"),
    create: (data: Record<string, unknown>) =>
      request<import("./types").ShippingMethod>("/shipping-methods", { method: "POST", body: JSON.stringify(data) }),
  },
  customers: {
    list: (params?: { search?: string; limit?: number; offset?: number }) =>
      request<import("./types").Customer[]>(`/customers${qs(params ?? {})}`),
    get: (id: number) => request<import("./types").Customer>(`/customers/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Customer>("/customers", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Customer>(`/customers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    lookup: (params: { email?: string; phone?: string }) =>
      request<import("./types").Customer>(`/customers/lookup${qs(params)}`),
    orders: (id: number) =>
      request<import("./types").OrderListItem[]>(`/customers/${id}/orders`),
  },
};
```

- [ ] **Step 3: Verify all frontend packages build**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm run build`
Expected: All packages build cleanly

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/shared/src/types.ts frontend/packages/shared/src/api.ts
git commit -m "feat: update API client with pagination, sorting, discount CRUD, locations, order search"
```

---

## Phase 4: Customer Store UX

### Task 9: Debounced Search and Product Sorting on ShopPage

**Files:**
- Modify: `frontend/packages/store/src/pages/ShopPage.tsx`

- [ ] **Step 1: Add debounce and sort controls**

Replace `frontend/packages/store/src/pages/ShopPage.tsx`:

```tsx
import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket, useDebounce, Spinner, Button, colors, baseStyles, spacing, radius, shadow } from "@openmarket/shared";
import type { Product, ProductListWithPrice } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

const SORT_OPTIONS = [
  { value: "", label: "Default" },
  { value: "title", label: "Name A-Z" },
  { value: "price_asc", label: "Price: Low to High" },
  { value: "price_desc", label: "Price: High to Low" },
  { value: "newest", label: "Newest" },
];

export function ShopPage() {
  const [products, setProducts] = useState<ProductListWithPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const { addItem } = useCart();

  const debouncedSearch = useDebounce(search, 300);
  const productTypes = [...new Set(products.map((p) => p.product_type).filter(Boolean))].sort();

  useEffect(() => {
    setLoading(true);
    setError("");
    api.products.list({
      status: "active",
      search: debouncedSearch || undefined,
      product_type: selectedType || undefined,
      sort_by: sortBy || undefined,
    })
      .then(setProducts)
      .catch(() => setError("Failed to load products. Please try again."))
      .finally(() => setLoading(false));
  }, [debouncedSearch, selectedType, sortBy]);

  const handleInventoryUpdate = useCallback(() => {}, []);
  useWebSocket(handleInventoryUpdate);

  const openProduct = async (id: number) => {
    setDetailLoading(true);
    try {
      const product = await api.products.get(id);
      setSelectedProduct(product);
    } catch {
      setError("Failed to load product details.");
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div style={{ ...baseStyles.container, display: "flex", gap: spacing.lg }}>
      {/* Sidebar */}
      <div style={{ width: 180, flexShrink: 0 }}>
        <h3 style={{ fontSize: "14px", color: colors.textSecondary, marginBottom: spacing.sm, textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Categories
        </h3>
        <div onClick={() => setSelectedType(null)} style={{
          padding: "6px 10px", cursor: "pointer", borderRadius: radius.sm, fontSize: "14px", marginBottom: "2px",
          background: selectedType === null ? colors.brandLight : "transparent",
          color: selectedType === null ? colors.brand : colors.textPrimary,
          fontWeight: selectedType === null ? 600 : 400,
        }}>All Products</div>
        {productTypes.map((t) => (
          <div key={t} onClick={() => setSelectedType(t)} style={{
            padding: "6px 10px", cursor: "pointer", borderRadius: radius.sm, fontSize: "14px", marginBottom: "2px", textTransform: "capitalize",
            background: selectedType === t ? colors.brandLight : "transparent",
            color: selectedType === t ? colors.brand : colors.textPrimary,
            fontWeight: selectedType === t ? 600 : 400,
          }}>{t}</div>
        ))}
      </div>

      {/* Main */}
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", gap: spacing.sm, marginBottom: spacing.lg }}>
          <input type="text" placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)}
            style={{ ...baseStyles.input, flex: 1 }} />
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}
            style={{ ...baseStyles.input, width: "auto", minWidth: 160, cursor: "pointer" }}>
            {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {error && (
          <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "10px 14px", borderRadius: radius.sm, fontSize: "14px", marginBottom: spacing.md }}>
            {error}
            <Button variant="ghost" size="sm" onClick={() => setError("")} style={{ marginLeft: spacing.sm }}>Dismiss</Button>
          </div>
        )}

        {loading ? (
          <Spinner label="Loading products..." />
        ) : products.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: colors.textSecondary }}>
            <p style={{ fontSize: "16px" }}>No products found</p>
            <p style={{ fontSize: "14px" }}>Try a different search or category</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: spacing.md }}>
            {products.map((p) => (
              <div key={p.id} onClick={() => openProduct(p.id)}
                style={{ ...baseStyles.card, cursor: "pointer", transition: "box-shadow 0.15s, border-color 0.15s", padding: 0, overflow: "hidden" }}
                onMouseEnter={(e) => { e.currentTarget.style.boxShadow = shadow.md; e.currentTarget.style.borderColor = colors.borderStrong; }}
                onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.borderColor = colors.border; }}>
                {p.image_url ? (
                  <img src={p.image_url} alt={p.title} loading="lazy" style={{ width: "100%", height: "160px", objectFit: "cover", display: "block" }} />
                ) : (
                  <div style={{ width: "100%", height: "160px", background: colors.surfaceMuted, display: "flex", alignItems: "center", justifyContent: "center", color: colors.textSecondary, fontSize: "13px" }}>No image</div>
                )}
                <div style={{ padding: spacing.md }}>
                  <div style={{ fontSize: "12px", color: colors.textSecondary, textTransform: "capitalize", marginBottom: "4px" }}>{p.product_type}</div>
                  <h3 style={{ margin: "0 0 8px", fontSize: "15px", fontWeight: 600 }}>{p.title}</h3>
                  {p.min_price && <div style={{ fontSize: "16px", fontWeight: 700, color: colors.brand }}>${p.min_price}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail Panel */}
      {(selectedProduct || detailLoading) && (
        <div style={{ width: 320, flexShrink: 0, ...baseStyles.card, alignSelf: "flex-start", position: "sticky" as const, top: `calc(${spacing.lg} + 56px)` }}>
          {detailLoading ? <Spinner label="Loading..." /> : selectedProduct && (
            <>
              {selectedProduct.images.length > 0 ? (
                <img src={selectedProduct.images[0].src} alt={selectedProduct.title} style={{ width: "100%", height: "200px", objectFit: "cover", borderRadius: radius.sm, marginBottom: spacing.md, display: "block" }} />
              ) : (
                <div style={{ width: "100%", height: "200px", background: colors.surfaceMuted, borderRadius: radius.sm, marginBottom: spacing.md, display: "flex", alignItems: "center", justifyContent: "center", color: colors.textSecondary, fontSize: "13px" }}>No image</div>
              )}
              <h2 style={{ margin: "0 0 4px", fontSize: "18px" }}>{selectedProduct.title}</h2>
              {selectedProduct.description && <p style={{ color: colors.textSecondary, fontSize: "14px", margin: "0 0 16px" }}>{selectedProduct.description}</p>}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {selectedProduct.variants.map((v) => (
                  <div key={v.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px", background: colors.surfaceMuted, borderRadius: radius.sm }}>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: "14px" }}>{v.title}</div>
                      <div style={{ fontSize: "15px", fontWeight: 700, color: colors.brand }}>${v.price}</div>
                    </div>
                    <Button variant="primary" size="sm" onClick={() => addItem(selectedProduct, v)}>Add</Button>
                  </div>
                ))}
              </div>
              <Button variant="ghost" size="sm" onClick={() => setSelectedProduct(null)} style={{ marginTop: "12px", width: "100%" }}>Close</Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify store builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/store run build`
Expected: Clean build

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/store/src/pages/ShopPage.tsx
git commit -m "feat: add debounced search, product sorting, error states, and lazy image loading to store"
```

---

### Task 10: Checkout Form Validation and Remove Confirmation

**Files:**
- Modify: `frontend/packages/store/src/pages/CartCheckoutPage.tsx`

- [ ] **Step 1: Add validation and confirmation**

Replace `frontend/packages/store/src/pages/CartCheckoutPage.tsx`:

```tsx
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, Button, ConfirmDialog, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { ShippingMethod, TaxRate } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

function validatePhone(phone: string): string | null {
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 7) return "Phone number must be at least 7 digits";
  return null;
}

function validateZip(zip: string): string | null {
  if (zip.length < 3) return "ZIP code is too short";
  return null;
}

export function CartCheckoutPage() {
  const { items, updateQuantity, removeItem, clearCart, total } = useCart();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [zip, setZip] = useState("");
  const [discountCode, setDiscountCode] = useState("");
  const [discount, setDiscount] = useState<{ type: string; value: number } | null>(null);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [orderNumber, setOrderNumber] = useState("");
  const [shippingMethods, setShippingMethods] = useState<ShippingMethod[]>([]);
  const [selectedShipping, setSelectedShipping] = useState<number | null>(null);
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [confirmRemove, setConfirmRemove] = useState<number | null>(null);

  useEffect(() => {
    api.shippingMethods.list().then((methods) => {
      setShippingMethods(methods);
      if (methods.length > 0) setSelectedShipping(methods[0].id);
    });
    api.taxRates.list().then(setTaxRates);
  }, []);

  const applyDiscount = async () => {
    try {
      const d = await api.discounts.lookup(discountCode);
      setDiscount({ type: d.discount_type, value: parseFloat(d.value) });
      setError("");
    } catch { setError("Invalid or expired discount code"); setDiscount(null); }
  };

  const subtotalAfterDiscount = discount
    ? discount.type === "percentage" ? total * (1 - discount.value / 100) : Math.max(0, total - discount.value)
    : total;

  const defaultTaxRate = taxRates.find((t) => t.is_default);
  const taxAmount = defaultTaxRate ? subtotalAfterDiscount * parseFloat(defaultTaxRate.rate) : 0;

  const selectedShippingMethod = shippingMethods.find((m) => m.id === selectedShipping);
  const shippingCost = selectedShippingMethod
    ? subtotalAfterDiscount >= parseFloat(selectedShippingMethod.min_order_amount)
      ? 0
      : parseFloat(selectedShippingMethod.price)
    : 0;

  const finalTotal = subtotalAfterDiscount + taxAmount + shippingCost;

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};
    if (!name.trim()) errors.name = "Name is required";
    const phoneErr = validatePhone(phone);
    if (phoneErr) errors.phone = phoneErr;
    if (!address.trim()) errors.address = "Address is required";
    if (!city.trim()) errors.city = "City is required";
    const zipErr = validateZip(zip);
    if (zipErr) errors.zip = zipErr;
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const canSubmit = name && phone && address && city && zip && items.length > 0 && !submitting;

  const placeOrder = async () => {
    if (!validateForm() || !canSubmit) return;
    setSubmitting(true);
    setError("");
    try {
      const order = await api.orders.create({
        source: "web", customer_name: name, customer_phone: phone,
        shipping_address: { address1: address, city, zip },
        line_items: items.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
        shipping_method_id: selectedShipping,
      });
      setOrderNumber(order.order_number);
      clearCart();
    } catch (e: any) { setError(e.message || "Failed to place order"); }
    finally { setSubmitting(false); }
  };

  const fieldInputStyle = (field: string) => ({
    ...baseStyles.input,
    borderColor: fieldErrors[field] ? colors.danger : undefined,
  });

  if (orderNumber) {
    return (
      <div style={{ ...baseStyles.container, maxWidth: 500, textAlign: "center", paddingTop: spacing.xl }}>
        <div style={baseStyles.card}>
          <div style={{ fontSize: "40px", marginBottom: spacing.md }}>&#10003;</div>
          <h2 style={{ margin: "0 0 8px" }}>Order Placed!</h2>
          <p style={{ color: colors.textSecondary }}>Your order number is:</p>
          <p style={{ fontSize: "20px", fontWeight: 700, color: colors.brand, margin: "8px 0 24px" }}>{orderNumber}</p>
          <p style={{ color: colors.textSecondary, fontSize: "14px", marginBottom: spacing.lg }}>Payment will be collected on delivery.</p>
          <Button variant="primary" onClick={() => navigate("/order-status")}>Track Order</Button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ ...baseStyles.container, maxWidth: 600 }}>
      <h2 style={{ marginBottom: spacing.lg }}>Cart</h2>
      {items.length === 0 ? (
        <div style={{ ...baseStyles.card, textAlign: "center", padding: spacing.xl }}>
          <p style={{ color: colors.textSecondary, fontSize: "16px" }}>Your cart is empty</p>
          <Button variant="primary" onClick={() => navigate("/")} style={{ marginTop: spacing.md }}>Browse Products</Button>
        </div>
      ) : (
        <>
          <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
            {items.map((item, i) => (
              <div key={item.variant.id} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "12px 0", borderBottom: i < items.length - 1 ? `1px solid ${colors.border}` : undefined,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: spacing.sm }}>
                  {item.product.images.length > 0 ? (
                    <img src={item.product.images[0].src} alt={item.product.title} style={{ width: 48, height: 48, objectFit: "cover", borderRadius: radius.sm, flexShrink: 0 }} />
                  ) : (
                    <div style={{ width: 48, height: 48, background: colors.surfaceMuted, borderRadius: radius.sm, flexShrink: 0 }} />
                  )}
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.product.title}</div>
                    <div style={{ color: colors.textSecondary, fontSize: "13px" }}>{item.variant.title} &middot; ${item.variant.price}</div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <Button variant="secondary" size="sm" onClick={() => updateQuantity(item.variant.id, item.quantity - 1)}>-</Button>
                  <span style={{ width: 28, textAlign: "center", fontWeight: 600 }}>{item.quantity}</span>
                  <Button variant="secondary" size="sm" onClick={() => updateQuantity(item.variant.id, item.quantity + 1)}>+</Button>
                  <Button variant="danger" size="sm" onClick={() => setConfirmRemove(item.variant.id)}>Remove</Button>
                </div>
              </div>
            ))}
          </div>

          <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
            <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
              <input placeholder="Discount code" value={discountCode} onChange={(e) => setDiscountCode(e.target.value)} style={baseStyles.input} />
              <Button variant="secondary" onClick={applyDiscount} style={{ flexShrink: 0 }}>Apply</Button>
            </div>
            {discount && (
              <div style={{ background: colors.successSurface, color: colors.success, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px" }}>
                Discount applied: {discount.type === "percentage" ? `${discount.value}%` : `$${discount.value}`} off
              </div>
            )}
          </div>

          {shippingMethods.length > 0 && (
            <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
              <h3 style={{ margin: "0 0 12px", fontSize: "16px" }}>Shipping Method</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {shippingMethods.map((method) => {
                  const isFree = subtotalAfterDiscount >= parseFloat(method.min_order_amount);
                  return (
                    <label key={method.id} style={{ display: "flex", alignItems: "flex-start", gap: "10px", cursor: "pointer" }}>
                      <input type="radio" name="shippingMethod" value={method.id} checked={selectedShipping === method.id}
                        onChange={() => setSelectedShipping(method.id)} style={{ marginTop: "2px" }} />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: "14px" }}>
                          {method.name} &mdash; {isFree ? <span style={{ color: colors.success }}>Free</span> : `$${parseFloat(method.price).toFixed(2)}`}
                        </div>
                        {parseFloat(method.min_order_amount) > 0 && (
                          <div style={{ color: colors.textSecondary, fontSize: "12px" }}>
                            Free on orders over ${parseFloat(method.min_order_amount).toFixed(2)}
                          </div>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: colors.textSecondary }}>Subtotal</span>
                <span>${subtotalAfterDiscount.toFixed(2)}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: colors.textSecondary }}>
                  Tax{defaultTaxRate ? ` (${(parseFloat(defaultTaxRate.rate) * 100).toFixed(0)}%)` : ""}
                </span>
                <span>${taxAmount.toFixed(2)}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: colors.textSecondary }}>Shipping</span>
                <span>{shippingCost === 0 ? <span style={{ color: colors.success }}>Free</span> : `$${shippingCost.toFixed(2)}`}</span>
              </div>
              <div style={{ borderTop: `1px solid ${colors.border}`, marginTop: "6px", paddingTop: "8px", display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 700, fontSize: "18px" }}>Total</span>
                <span style={{ fontWeight: 700, fontSize: "18px" }}>${finalTotal.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div style={baseStyles.card}>
            <h3 style={{ margin: "0 0 16px", fontSize: "16px" }}>Delivery Details</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div>
                <input placeholder="Full name *" value={name} onChange={(e) => { setName(e.target.value); setFieldErrors((p) => ({ ...p, name: "" })); }} style={fieldInputStyle("name")} />
                {fieldErrors.name && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.name}</div>}
              </div>
              <div>
                <input placeholder="Phone * (e.g. 010-1234-5678)" value={phone} onChange={(e) => { setPhone(e.target.value); setFieldErrors((p) => ({ ...p, phone: "" })); }} style={fieldInputStyle("phone")} />
                {fieldErrors.phone && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.phone}</div>}
              </div>
              <div>
                <input placeholder="Address *" value={address} onChange={(e) => { setAddress(e.target.value); setFieldErrors((p) => ({ ...p, address: "" })); }} style={fieldInputStyle("address")} />
                {fieldErrors.address && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.address}</div>}
              </div>
              <div style={{ display: "flex", gap: "10px" }}>
                <div style={{ flex: 1 }}>
                  <input placeholder="City *" value={city} onChange={(e) => { setCity(e.target.value); setFieldErrors((p) => ({ ...p, city: "" })); }} style={fieldInputStyle("city")} />
                  {fieldErrors.city && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.city}</div>}
                </div>
                <div style={{ width: 120 }}>
                  <input placeholder="ZIP *" value={zip} onChange={(e) => { setZip(e.target.value); setFieldErrors((p) => ({ ...p, zip: "" })); }} style={fieldInputStyle("zip")} />
                  {fieldErrors.zip && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.zip}</div>}
                </div>
              </div>
            </div>
            <p style={{ color: colors.textSecondary, fontSize: "13px", margin: "12px 0 4px" }}>Payment will be collected on delivery.</p>
            {error && <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px", marginTop: "8px" }}>{error}</div>}
            <Button variant="primary" size="lg" fullWidth loading={submitting} disabled={!canSubmit} onClick={placeOrder} style={{ marginTop: spacing.md }}>
              Place Order — ${finalTotal.toFixed(2)}
            </Button>
          </div>
        </>
      )}

      {confirmRemove !== null && (
        <ConfirmDialog
          title="Remove item"
          message="Are you sure you want to remove this item from your cart?"
          confirmLabel="Remove"
          variant="danger"
          onConfirm={() => { removeItem(confirmRemove); setConfirmRemove(null); }}
          onCancel={() => setConfirmRemove(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify store builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/store run build`
Expected: Clean build

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/store/src/pages/CartCheckoutPage.tsx
git commit -m "feat: add checkout form validation and cart item removal confirmation"
```

---

### Task 11: Wrap Store App with ToastProvider

**Files:**
- Modify: `frontend/packages/store/src/App.tsx`

- [ ] **Step 1: Read current App.tsx and wrap with ToastProvider**

In `frontend/packages/store/src/App.tsx`, add the ToastProvider import and wrap the existing content:

Add import:
```tsx
import { ToastProvider } from "@openmarket/shared";
```

Wrap the return value's outer `<div style={baseStyles.page}>` children inside `<ToastProvider>...</ToastProvider>`.

The existing `CartProvider` stays inside `ToastProvider`.

- [ ] **Step 2: Verify store builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/store run build`
Expected: Clean build

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/store/src/App.tsx
git commit -m "feat: wrap store app with ToastProvider"
```

---

## Phase 5: Admin Dashboard UX

### Task 12: Admin Customer Management Page

**Files:**
- Create: `frontend/packages/admin/src/pages/CustomersPage.tsx`
- Modify: `frontend/packages/admin/src/App.tsx`

- [ ] **Step 1: Create CustomersPage**

```tsx
// frontend/packages/admin/src/pages/CustomersPage.tsx
import { useEffect, useState } from "react";
import { api, useDebounce, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Customer, OrderListItem } from "@openmarket/shared";

export function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 300);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedOrders, setExpandedOrders] = useState<OrderListItem[]>([]);

  useEffect(() => {
    setLoading(true);
    api.customers.list({ search: debouncedSearch || undefined })
      .then(setCustomers)
      .finally(() => setLoading(false));
  }, [debouncedSearch]);

  const expand = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    setExpandedOrders(await api.customers.orders(id));
  };

  return (
    <div style={baseStyles.container}>
      <h2 style={{ marginBottom: spacing.lg }}>Customers</h2>
      <input placeholder="Search by name, email, or phone..." value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ ...baseStyles.input, marginBottom: spacing.lg }} />

      {loading ? <Spinner label="Loading customers..." /> : customers.length === 0 ? (
        <div style={{ ...baseStyles.card, textAlign: "center", padding: spacing.xl, color: colors.textSecondary }}>
          {search ? "No customers match your search" : "No customers yet"}
        </div>
      ) : (
        <div style={{ ...baseStyles.card, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
            <thead>
              <tr style={{ background: colors.surfaceMuted, textAlign: "left" }}>
                <th style={{ padding: "10px 16px" }}>Name</th>
                <th style={{ padding: "10px 16px" }}>Email</th>
                <th style={{ padding: "10px 16px" }}>Phone</th>
                <th style={{ padding: "10px 16px" }}>Addresses</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tbody key={c.id}>
                  <tr onClick={() => expand(c.id)} style={{ cursor: "pointer", borderBottom: `1px solid ${colors.border}`, background: expandedId === c.id ? colors.surfaceMuted : colors.surface }}>
                    <td style={{ padding: "10px 16px", fontWeight: 500 }}>{c.first_name} {c.last_name}</td>
                    <td style={{ padding: "10px 16px", color: colors.textSecondary }}>{c.email || "---"}</td>
                    <td style={{ padding: "10px 16px" }}>{c.phone || "---"}</td>
                    <td style={{ padding: "10px 16px", color: colors.textSecondary }}>{c.addresses.length}</td>
                  </tr>
                  {expandedId === c.id && (
                    <tr>
                      <td colSpan={4} style={{ padding: "16px", background: colors.surfaceMuted, borderBottom: `1px solid ${colors.border}` }}>
                        {c.addresses.length > 0 && (
                          <div style={{ marginBottom: spacing.md }}>
                            <strong style={{ fontSize: "13px", color: colors.textSecondary }}>Addresses</strong>
                            {c.addresses.map((a) => (
                              <div key={a.id} style={{ fontSize: "13px", marginTop: "4px" }}>
                                {a.address1}, {a.city} {a.zip} {a.is_default && <span style={{ color: colors.brand, fontSize: "11px" }}>(default)</span>}
                              </div>
                            ))}
                          </div>
                        )}
                        <strong style={{ fontSize: "13px", color: colors.textSecondary }}>Order History ({expandedOrders.length})</strong>
                        {expandedOrders.length === 0 ? (
                          <div style={{ fontSize: "13px", color: colors.textSecondary, marginTop: "4px" }}>No orders</div>
                        ) : (
                          <div style={{ marginTop: "4px" }}>
                            {expandedOrders.map((o) => (
                              <div key={o.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", padding: "4px 0" }}>
                                <span>{o.order_number}</span>
                                <span>${o.total_price} &middot; {o.fulfillment_status}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </tbody>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add Customers route and nav link to admin App.tsx**

In `frontend/packages/admin/src/App.tsx`:

Add import:
```tsx
import { CustomersPage } from "./pages/CustomersPage";
```

Add nav link after the Orders link (line 22):
```tsx
<Link to="/customers" style={linkStyle("/customers")}>Customers</Link>
```

Add route after Orders route (before `</Routes>`):
```tsx
<Route path="/customers" element={<CustomersPage />} />
```

- [ ] **Step 3: Verify admin builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/admin run build`
Expected: Clean build

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/admin/src/pages/CustomersPage.tsx frontend/packages/admin/src/App.tsx
git commit -m "feat: add admin customer management page with search and order history"
```

---

### Task 13: Admin Settings Page (Tax, Shipping, Discounts, Locations)

**Files:**
- Create: `frontend/packages/admin/src/pages/SettingsPage.tsx`
- Modify: `frontend/packages/admin/src/App.tsx`

- [ ] **Step 1: Create SettingsPage**

```tsx
// frontend/packages/admin/src/pages/SettingsPage.tsx
import { useEffect, useState } from "react";
import { api, Button, Spinner, useToast, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { TaxRate, ShippingMethod, Discount, Location } from "@openmarket/shared";

export function SettingsPage() {
  const { toast } = useToast();
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [shippingMethods, setShippingMethods] = useState<ShippingMethod[]>([]);
  const [discounts, setDiscounts] = useState<Discount[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);

  // Tax form
  const [taxName, setTaxName] = useState("");
  const [taxRate, setTaxRate] = useState("");
  const [taxRegion, setTaxRegion] = useState("");
  const [taxDefault, setTaxDefault] = useState(false);

  // Shipping form
  const [shipName, setShipName] = useState("");
  const [shipPrice, setShipPrice] = useState("");
  const [shipMinOrder, setShipMinOrder] = useState("");

  // Discount form
  const [discCode, setDiscCode] = useState("");
  const [discType, setDiscType] = useState("percentage");
  const [discValue, setDiscValue] = useState("");
  const [discStart, setDiscStart] = useState("");
  const [discEnd, setDiscEnd] = useState("");

  const loadAll = async () => {
    setLoading(true);
    const [t, s, d, l] = await Promise.all([
      api.taxRates.list(), api.shippingMethods.list(), api.discounts.list(), api.locations.list(),
    ]);
    setTaxRates(t); setShippingMethods(s); setDiscounts(d); setLocations(l);
    setLoading(false);
  };

  useEffect(() => { loadAll(); }, []);

  const createTax = async () => {
    if (!taxName || !taxRate) return;
    await api.taxRates.create({ name: taxName, rate: taxRate, region: taxRegion, is_default: taxDefault });
    setTaxName(""); setTaxRate(""); setTaxRegion(""); setTaxDefault(false);
    toast("Tax rate created");
    loadAll();
  };

  const createShipping = async () => {
    if (!shipName || !shipPrice) return;
    await api.shippingMethods.create({ name: shipName, price: shipPrice, min_order_amount: shipMinOrder || "0", is_active: true });
    setShipName(""); setShipPrice(""); setShipMinOrder("");
    toast("Shipping method created");
    loadAll();
  };

  const createDiscount = async () => {
    if (!discCode || !discValue || !discStart || !discEnd) return;
    await api.discounts.create({
      code: discCode, discount_type: discType, value: discValue,
      starts_at: new Date(discStart).toISOString(), ends_at: new Date(discEnd).toISOString(),
    });
    setDiscCode(""); setDiscValue(""); setDiscStart(""); setDiscEnd("");
    toast("Discount created");
    loadAll();
  };

  const deleteDiscount = async (id: number) => {
    await api.discounts.delete(id);
    toast("Discount deleted");
    loadAll();
  };

  const sectionTitle: React.CSSProperties = { margin: `0 0 ${spacing.md}`, fontSize: "16px" };
  const formRow: React.CSSProperties = { display: "flex", gap: spacing.sm, marginBottom: spacing.sm };

  if (loading) return <div style={baseStyles.container}><Spinner label="Loading settings..." /></div>;

  return (
    <div style={baseStyles.container}>
      <h2 style={{ marginBottom: spacing.lg }}>Settings</h2>

      {/* Locations */}
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <h3 style={sectionTitle}>Locations</h3>
        {locations.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: "14px" }}>No locations configured</div>
        ) : locations.map((l) => (
          <div key={l.id} style={{ fontSize: "14px", padding: "4px 0" }}>
            <strong>{l.name}</strong> {l.address && <span style={{ color: colors.textSecondary }}>--- {l.address}</span>}
          </div>
        ))}
      </div>

      {/* Tax Rates */}
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <h3 style={sectionTitle}>Tax Rates</h3>
        {taxRates.map((t) => (
          <div key={t.id} style={{ fontSize: "14px", padding: "4px 0", display: "flex", justifyContent: "space-between" }}>
            <span><strong>{t.name}</strong> --- {(parseFloat(t.rate) * 100).toFixed(1)}% {t.region && `(${t.region})`}</span>
            {t.is_default && <span style={{ color: colors.brand, fontSize: "12px", fontWeight: 600 }}>DEFAULT</span>}
          </div>
        ))}
        <div style={{ ...formRow, marginTop: spacing.md }}>
          <input placeholder="Name *" value={taxName} onChange={(e) => setTaxName(e.target.value)} style={{ ...baseStyles.input, flex: 1 }} />
          <input placeholder="Rate (e.g. 0.10)" value={taxRate} onChange={(e) => setTaxRate(e.target.value)} style={{ ...baseStyles.input, width: 120 }} />
          <input placeholder="Region" value={taxRegion} onChange={(e) => setTaxRegion(e.target.value)} style={{ ...baseStyles.input, width: 100 }} />
          <label style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "13px", whiteSpace: "nowrap" }}>
            <input type="checkbox" checked={taxDefault} onChange={(e) => setTaxDefault(e.target.checked)} /> Default
          </label>
          <Button variant="primary" size="sm" onClick={createTax}>Add</Button>
        </div>
      </div>

      {/* Shipping Methods */}
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <h3 style={sectionTitle}>Shipping Methods</h3>
        {shippingMethods.map((s) => (
          <div key={s.id} style={{ fontSize: "14px", padding: "4px 0" }}>
            <strong>{s.name}</strong> --- ${s.price} {parseFloat(s.min_order_amount) > 0 && `(free over $${s.min_order_amount})`}
          </div>
        ))}
        <div style={{ ...formRow, marginTop: spacing.md }}>
          <input placeholder="Name *" value={shipName} onChange={(e) => setShipName(e.target.value)} style={{ ...baseStyles.input, flex: 1 }} />
          <input placeholder="Price *" value={shipPrice} onChange={(e) => setShipPrice(e.target.value)} style={{ ...baseStyles.input, width: 100 }} />
          <input placeholder="Free above $" value={shipMinOrder} onChange={(e) => setShipMinOrder(e.target.value)} style={{ ...baseStyles.input, width: 120 }} />
          <Button variant="primary" size="sm" onClick={createShipping}>Add</Button>
        </div>
      </div>

      {/* Discounts */}
      <div style={baseStyles.card}>
        <h3 style={sectionTitle}>Discount Codes</h3>
        {discounts.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: "14px", marginBottom: spacing.md }}>No discounts configured</div>
        ) : (
          <div style={{ marginBottom: spacing.md }}>
            {discounts.map((d) => (
              <div key={d.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: `1px solid ${colors.border}`, fontSize: "14px" }}>
                <div>
                  <strong>{d.code}</strong> --- {d.discount_type === "percentage" ? `${d.value}%` : `$${d.value}`} off
                  <span style={{ color: colors.textSecondary, fontSize: "12px", marginLeft: spacing.sm }}>
                    {new Date(d.starts_at).toLocaleDateString()} - {new Date(d.ends_at).toLocaleDateString()}
                  </span>
                </div>
                <Button variant="danger" size="sm" onClick={() => deleteDiscount(d.id)}>Delete</Button>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: spacing.sm }}>
          <div style={formRow}>
            <input placeholder="Code *" value={discCode} onChange={(e) => setDiscCode(e.target.value)} style={{ ...baseStyles.input, flex: 1 }} />
            <select value={discType} onChange={(e) => setDiscType(e.target.value)} style={{ ...baseStyles.input, width: 130 }}>
              <option value="percentage">Percentage</option>
              <option value="fixed">Fixed Amount</option>
            </select>
            <input placeholder="Value *" value={discValue} onChange={(e) => setDiscValue(e.target.value)} style={{ ...baseStyles.input, width: 100 }} />
          </div>
          <div style={formRow}>
            <label style={{ fontSize: "13px", color: colors.textSecondary, display: "flex", alignItems: "center", gap: "4px" }}>
              Start: <input type="date" value={discStart} onChange={(e) => setDiscStart(e.target.value)} style={{ ...baseStyles.input, width: "auto" }} />
            </label>
            <label style={{ fontSize: "13px", color: colors.textSecondary, display: "flex", alignItems: "center", gap: "4px" }}>
              End: <input type="date" value={discEnd} onChange={(e) => setDiscEnd(e.target.value)} style={{ ...baseStyles.input, width: "auto" }} />
            </label>
            <Button variant="primary" size="sm" onClick={createDiscount}>Add Discount</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add Settings route and nav link to admin App.tsx**

In `frontend/packages/admin/src/App.tsx`:

Add import:
```tsx
import { SettingsPage } from "./pages/SettingsPage";
import { ToastProvider } from "@openmarket/shared";
```

Add nav link:
```tsx
<Link to="/settings" style={linkStyle("/settings")}>Settings</Link>
```

Add route:
```tsx
<Route path="/settings" element={<SettingsPage />} />
```

Wrap the outer `<div style={baseStyles.page}>` content inside `<ToastProvider>`:
```tsx
return (
  <ToastProvider>
    <div style={baseStyles.page}>
      ...existing content...
    </div>
  </ToastProvider>
);
```

- [ ] **Step 3: Verify admin builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/admin run build`
Expected: Clean build

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/admin/src/pages/SettingsPage.tsx frontend/packages/admin/src/App.tsx
git commit -m "feat: add admin settings page with tax, shipping, discount, and location management"
```

---

### Task 14: Toast and Confirmation Dialogs on Inventory Actions

**Files:**
- Modify: `frontend/packages/admin/src/pages/ProductsInventoryPage.tsx`

- [ ] **Step 1: Add toast, confirm dialog, and location selector to ProductsInventoryPage**

In `frontend/packages/admin/src/pages/ProductsInventoryPage.tsx`:

Add to imports:
```tsx
import { api, useWebSocket, useToast, useDebounce, Button, Spinner, ConfirmDialog, colors, baseStyles, spacing, radius, BarcodeScanner, OCRScanner } from "@openmarket/shared";
import type { Product, ProductListWithPrice, InventoryLevel, Location } from "@openmarket/shared";
```

Add inside the component function (after existing state):
```tsx
const { toast } = useToast();
const [locations, setLocations] = useState<Location[]>([]);
const [selectedLocationId, setSelectedLocationId] = useState<number>(1);
const [confirmAction, setConfirmAction] = useState<{ message: string; onConfirm: () => void } | null>(null);
const debouncedSearch = useDebounce(search, 300);
```

Key changes to make:
1. Replace `search` dependency in `useEffect` with `debouncedSearch`
2. Load locations on mount: `api.locations.list().then((locs) => { setLocations(locs); if (locs.length > 0) setSelectedLocationId(locs[0].id); });`
3. Replace hardcoded `1` in `loadInventory` and `adjustStock`/`setStock` with `selectedLocationId`
4. Add toast calls after `adjustStock`, `setStock`, and `createProduct`
5. Wrap `adjustStock` calls in confirmation: `setConfirmAction({ message: "Adjust stock by X?", onConfirm: () => adjustStock(...) })`
6. Add location selector dropdown above the table
7. Render `confirmAction && <ConfirmDialog .../>` at the end

The adjustStock function becomes:
```tsx
const adjustStock = async (inventoryItemId: number, delta: number) => {
  try {
    await api.inventory.adjust({ inventory_item_id: inventoryItemId, location_id: selectedLocationId, available_adjustment: delta });
    await loadInventory();
    toast(`Stock adjusted by ${delta > 0 ? "+" : ""}${delta}`);
  } catch { toast("Failed to adjust stock", "error"); }
};
```

The setStock function becomes:
```tsx
const setStock = async (inventoryItemId: number) => {
  const val = parseInt(stockInputs[inventoryItemId] || "");
  if (isNaN(val) || val < 0) return;
  try {
    await api.inventory.set({ inventory_item_id: inventoryItemId, location_id: selectedLocationId, available: val });
    setStockInputs((p) => ({ ...p, [inventoryItemId]: "" }));
    await loadInventory();
    toast(`Stock set to ${val}`);
  } catch { toast("Failed to set stock", "error"); }
};
```

The createProduct function gets a toast:
```tsx
const createProduct = async () => {
  if (!newTitle || !newHandle || !newPrice) return;
  try {
    await api.products.create({
      title: newTitle, handle: newHandle, product_type: newType,
      variants: [{ title: "Default", price: newPrice, barcode: newBarcode }],
    });
    setNewTitle(""); setNewHandle(""); setNewType(""); setNewPrice(""); setNewBarcode("");
    setShowCreate(false);
    loadProducts(); loadInventory();
    toast("Product created");
  } catch (e: any) { toast(e.message || "Failed to create product", "error"); }
};
```

Add location selector before the search input:
```tsx
{locations.length > 1 && (
  <div style={{ marginBottom: spacing.md }}>
    <label style={{ fontSize: "13px", color: colors.textSecondary, marginRight: spacing.sm }}>Location:</label>
    <select value={selectedLocationId} onChange={(e) => setSelectedLocationId(Number(e.target.value))}
      style={{ ...baseStyles.input, width: "auto", display: "inline-block" }}>
      {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
    </select>
  </div>
)}
```

Add at end of return (before closing `</div>`):
```tsx
{confirmAction && (
  <ConfirmDialog
    title="Confirm Action"
    message={confirmAction.message}
    onConfirm={() => { confirmAction.onConfirm(); setConfirmAction(null); }}
    onCancel={() => setConfirmAction(null)}
  />
)}
```

- [ ] **Step 2: Verify admin builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/admin run build`
Expected: Clean build

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/admin/src/pages/ProductsInventoryPage.tsx
git commit -m "feat: add toast notifications, confirmation dialogs, and location selector to inventory page"
```

---

### Task 15: Order Search, Filtering, and CSV Export on OrdersPage

**Files:**
- Create: `frontend/packages/shared/src/exportCsv.ts`
- Modify: `frontend/packages/shared/src/index.ts`
- Modify: `frontend/packages/admin/src/pages/OrdersPage.tsx`

- [ ] **Step 1: Create CSV export utility**

```ts
// frontend/packages/shared/src/exportCsv.ts
export function exportCsv(filename: string, headers: string[], rows: string[][]) {
  const escape = (val: string) => `"${val.replace(/"/g, '""')}"`;
  const lines = [headers.map(escape).join(",")];
  for (const row of rows) {
    lines.push(row.map(escape).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 2: Export from shared index**

Add to `frontend/packages/shared/src/index.ts`:
```ts
export { exportCsv } from "./exportCsv";
```

- [ ] **Step 3: Update OrdersPage with search, source filter, date filter, and export**

Replace `frontend/packages/admin/src/pages/OrdersPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api, useDebounce, exportCsv, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Order, OrderListItem } from "@openmarket/shared";

export function OrdersPage() {
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"unfulfilled" | "fulfilled">("unfulfilled");
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const debouncedSearch = useDebounce(search, 300);
  const [expandedOrder, setExpandedOrder] = useState<Order | null>(null);

  const loadOrders = async () => {
    setLoading(true);
    setOrders(await api.orders.list({
      fulfillment_status: tab,
      search: debouncedSearch || undefined,
      source: sourceFilter || undefined,
    }));
    setLoading(false);
  };

  useEffect(() => { loadOrders(); }, [tab, debouncedSearch, sourceFilter]);

  const expandOrder = async (id: number) => {
    if (expandedOrder?.id === id) { setExpandedOrder(null); return; }
    setExpandedOrder(await api.orders.get(id));
  };

  const fulfill = async (orderId: number) => {
    await api.fulfillments.create(orderId, { status: "delivered" });
    await loadOrders();
    setExpandedOrder(null);
  };

  const handleExport = () => {
    exportCsv(
      `orders-${tab}-${new Date().toISOString().slice(0, 10)}.csv`,
      ["Order #", "Source", "Total", "Date", "Status"],
      orders.map((o) => [o.order_number, o.source, `$${o.total_price}`, new Date(o.created_at).toLocaleDateString(), o.fulfillment_status]),
    );
  };

  const tabStyle = (active: boolean) => ({
    padding: "7px 16px", borderRadius: radius.sm, fontSize: "14px",
    fontWeight: active ? (600 as const) : (400 as const),
    background: active ? colors.brand : "transparent",
    color: active ? "#fff" : colors.textPrimary,
    border: `1px solid ${active ? colors.brand : colors.borderStrong}`,
    cursor: "pointer" as const,
  });

  return (
    <div style={baseStyles.container}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
        <h2 style={{ margin: 0 }}>Orders</h2>
        <Button variant="secondary" size="sm" onClick={handleExport} disabled={orders.length === 0}>Export CSV</Button>
      </div>

      <div style={{ display: "flex", gap: spacing.sm, marginBottom: spacing.lg, flexWrap: "wrap" }}>
        <button onClick={() => setTab("unfulfilled")} style={tabStyle(tab === "unfulfilled")}>Unfulfilled</button>
        <button onClick={() => setTab("fulfilled")} style={tabStyle(tab === "fulfilled")}>Fulfilled</button>
        <div style={{ flex: 1 }} />
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}
          style={{ ...baseStyles.input, width: "auto", minWidth: 100 }}>
          <option value="">All Sources</option>
          <option value="web">Web</option>
          <option value="pos">POS</option>
        </select>
        <input placeholder="Search order #..." value={search} onChange={(e) => setSearch(e.target.value)}
          style={{ ...baseStyles.input, width: 200 }} />
      </div>

      {loading ? <Spinner label="Loading orders..." /> : orders.length === 0 ? (
        <div style={{ ...baseStyles.card, textAlign: "center", padding: spacing.xl, color: colors.textSecondary }}>
          No {tab} orders{search && " matching your search"}
        </div>
      ) : (
        <div style={{ ...baseStyles.card, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
            <thead>
              <tr style={{ background: colors.surfaceMuted, textAlign: "left" }}>
                <th style={{ padding: "10px 16px" }}>Order #</th>
                <th style={{ padding: "10px 16px" }}>Source</th>
                <th style={{ padding: "10px 16px" }}>Total</th>
                <th style={{ padding: "10px 16px" }}>Date</th>
                <th style={{ padding: "10px 16px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tbody key={o.id}>
                  <tr onClick={() => expandOrder(o.id)} style={{ cursor: "pointer", borderBottom: `1px solid ${colors.border}`, background: expandedOrder?.id === o.id ? colors.surfaceMuted : colors.surface }}>
                    <td style={{ padding: "10px 16px", fontWeight: 500 }}>{o.order_number}</td>
                    <td style={{ padding: "10px 16px" }}>
                      <span style={{ padding: "2px 8px", borderRadius: "4px", fontSize: "12px", fontWeight: 600, background: o.source === "pos" ? colors.brandLight : colors.warningSurface, color: o.source === "pos" ? colors.brand : colors.warning }}>
                        {o.source.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: "10px 16px" }}>${o.total_price}</td>
                    <td style={{ padding: "10px 16px", color: colors.textSecondary }}>{new Date(o.created_at).toLocaleDateString()}</td>
                    <td style={{ padding: "10px 16px" }}>{o.fulfillment_status}</td>
                  </tr>
                  {expandedOrder?.id === o.id && (
                    <tr>
                      <td colSpan={5} style={{ padding: "16px", background: colors.surfaceMuted, borderBottom: `1px solid ${colors.border}` }}>
                        <div style={{ fontSize: "13px" }}>
                          {expandedOrder.line_items.map((li) => (
                            <div key={li.id} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                              <span>{li.title} &times; {li.quantity}</span>
                              <span>${(parseFloat(li.price) * li.quantity).toFixed(2)}</span>
                            </div>
                          ))}
                        </div>
                        {expandedOrder.shipping_address && (
                          <div style={{ marginTop: "12px", fontSize: "13px", color: colors.textSecondary }}>
                            Deliver to: {expandedOrder.shipping_address.address1}, {expandedOrder.shipping_address.city} {expandedOrder.shipping_address.zip}
                          </div>
                        )}
                        {expandedOrder.fulfillment_status === "unfulfilled" && (
                          <Button variant="primary" size="sm" onClick={() => fulfill(o.id)} style={{ marginTop: "12px" }}>
                            Mark as Fulfilled
                          </Button>
                        )}
                      </td>
                    </tr>
                  )}
                </tbody>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify admin builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/admin run build`
Expected: Clean build

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/shared/src/exportCsv.ts frontend/packages/shared/src/index.ts frontend/packages/admin/src/pages/OrdersPage.tsx
git commit -m "feat: add order search, source filtering, and CSV export to admin orders page"
```

---

## Phase 6: POS UX

### Task 16: POS Header and Navigation

**Files:**
- Modify: `frontend/packages/pos/src/App.tsx`

- [ ] **Step 1: Add header with store name, clock, and navigation**

Replace `frontend/packages/pos/src/App.tsx`:

```tsx
import { useState, useEffect } from "react";
import { SalePage } from "./pages/SalePage";
import { font, colors, spacing, baseStyles, ToastProvider } from "@openmarket/shared";

function Clock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return <span>{time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>;
}

export function App() {
  return (
    <ToastProvider>
      <div style={{ fontFamily: font.body, display: "flex", flexDirection: "column", height: "100vh" }}>
        <nav style={{
          ...baseStyles.nav,
          height: "44px",
          padding: `0 ${spacing.md}`,
          borderBottom: `1px solid ${colors.border}`,
          justifyContent: "space-between",
        }}>
          <span style={{ fontWeight: 700, color: colors.brand, fontSize: "1rem" }}>OpenMarket POS</span>
          <div style={{ display: "flex", alignItems: "center", gap: spacing.lg, fontSize: "13px", color: colors.textSecondary }}>
            <Clock />
            <span>{new Date().toLocaleDateString()}</span>
          </div>
        </nav>
        <div style={{ flex: 1, overflow: "hidden" }}>
          <SalePage />
        </div>
      </div>
    </ToastProvider>
  );
}
```

- [ ] **Step 2: Update SalePage to remove height: 100vh (now handled by App)**

In `frontend/packages/pos/src/pages/SalePage.tsx`, change line 87:
```tsx
<div style={{ display: "flex", height: "100%" }}>
```
(Change `height: "100vh"` to `height: "100%"`)

- [ ] **Step 3: Verify POS builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/pos run build`
Expected: Clean build

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/pos/src/App.tsx frontend/packages/pos/src/pages/SalePage.tsx
git commit -m "feat: add POS header with store name, clock, and ToastProvider"
```

---

### Task 17: POS Keyboard Shortcuts and Toast Notifications

**Files:**
- Modify: `frontend/packages/pos/src/pages/SalePage.tsx`

- [ ] **Step 1: Add keyboard shortcuts and toast**

In `frontend/packages/pos/src/pages/SalePage.tsx`:

Add imports:
```tsx
import { api, useWebSocket, useToast, Button, ConfirmDialog, colors, baseStyles, spacing, radius, BarcodeScanner } from "@openmarket/shared";
```

Add inside the component (after existing state):
```tsx
const { toast } = useToast();
const [confirmVoid, setConfirmVoid] = useState(false);
```

Add keyboard shortcut effect:
```tsx
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    // Escape: clear error or close receipt
    if (e.key === "Escape") {
      if (receiptData) { setReceiptData(null); barcodeRef.current?.focus(); }
      else if (error) { setError(""); }
      else if (showReturn) { setShowReturn(false); }
      return;
    }
    // F8: Complete sale
    if (e.key === "F8" && saleItems.length > 0 && !receiptData) {
      e.preventDefault();
      completeSale();
      return;
    }
    // F4: Void sale
    if (e.key === "F4" && saleItems.length > 0) {
      e.preventDefault();
      setConfirmVoid(true);
      return;
    }
    // F9: Returns
    if (e.key === "F9") {
      e.preventDefault();
      setShowReturn(true);
      return;
    }
  };
  window.addEventListener("keydown", handleKeyDown);
  return () => window.removeEventListener("keydown", handleKeyDown);
}, [saleItems.length, receiptData, error, showReturn]);
```

Replace voidSale to use ConfirmDialog:
```tsx
const voidSale = () => setConfirmVoid(true);
const doVoidSale = () => { setSaleItems([]); setConfirmVoid(false); toast("Sale voided"); barcodeRef.current?.focus(); };
```

Update completeSale to use toast:
```tsx
const completeSale = async () => {
  setError("");
  try {
    const order = await api.orders.create({ source: "pos", line_items: saleItems.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })) });
    const receiptItems: ReceiptItem[] = saleItems.map((i) => ({
      productTitle: i.productTitle, variantTitle: i.variant.title,
      quantity: i.quantity, price: i.variant.price,
    }));
    const receiptTotal = saleItems.reduce((sum, i) => sum + parseFloat(i.variant.price) * i.quantity, 0);
    setSaleItems([]);
    setReceiptData({ orderNumber: String(order.order_number), items: receiptItems, total: receiptTotal });
    toast("Sale completed");
  } catch (e: any) { setError(e.message); toast("Sale failed", "error"); }
};
```

Add keyboard shortcut hints to buttons. Update the "Void Sale" button:
```tsx
<Button variant="danger" size="sm" onClick={voidSale}>Void (F4)</Button>
```

Update the "Complete Sale" button:
```tsx
<Button variant="primary" size="lg" fullWidth disabled={saleItems.length === 0} onClick={completeSale}
  style={{ background: "#1A7F37", padding: "14px", fontSize: "18px" }}>
  Complete Sale (F8)
</Button>
```

Update the "Returns" button:
```tsx
<Button variant="secondary" size="sm" onClick={() => setShowReturn(true)}>Returns (F9)</Button>
```

Add ConfirmDialog at end of return (before closing `</div>`):
```tsx
{confirmVoid && (
  <ConfirmDialog
    title="Void Sale"
    message="All items will be cleared from the current sale. This cannot be undone."
    confirmLabel="Void Sale"
    variant="danger"
    onConfirm={doVoidSale}
    onCancel={() => setConfirmVoid(false)}
  />
)}
```

- [ ] **Step 2: Verify POS builds**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm --filter @openmarket/pos run build`
Expected: Clean build

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/pos/src/pages/SalePage.tsx
git commit -m "feat: add POS keyboard shortcuts (F4/F8/F9/Esc), toast notifications, and confirmation dialog"
```

---

## Deferred to Separate Plans

These high-priority items require significant standalone work and should each be their own plan:

1. **Inventory Audit Trail** - New `inventory_logs` DB table, Alembic migration, service layer changes, API endpoints, admin UI for viewing history. Large backend-heavy effort.
2. **Account Page Improvements** - Address book management, reorder from past orders, account settings. Requires new backend endpoints for address CRUD and reorder.
3. **Order Status Timeline** - Fulfillment tracking with shipping carrier, tracking URL, estimated delivery. Requires new DB fields and potentially external shipping API integration.
4. **Receipt Reprint** - POS ability to look up and reprint past order receipts. Requires order lookup UI in POS context.

---

## Phase 7: Final Build Verification

### Task 18: Full Build and Test Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd /Users/huijokim/personal/openmarket/backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Run full frontend build**

Run: `cd /Users/huijokim/personal/openmarket/frontend && pnpm run build`
Expected: All 3 packages (store, admin, pos) build cleanly

- [ ] **Step 3: Review all changes**

Run: `git diff main --stat`
Verify the list of changed files matches the plan.

- [ ] **Step 4: Final commit if any remaining changes**

```bash
git status
# If any unstaged changes remain, add and commit them
```
