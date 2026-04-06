# Feedback Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address the critical/dealbreaker feedback from all 3 reviewers (UX, Visual, Manager) to raise the product from prototype to usable MVP.

**Architecture:** Backend gets new endpoints (barcode lookup, order-number lookup, product CRUD for admin). Frontend gets a design token system, shared components, and page-level fixes across all 3 apps. Changes are additive — existing tests must keep passing.

**Tech Stack:** FastAPI, SQLAlchemy, React, TypeScript, Vite

**Feedback sources:** `docs/feedbacks/01-ux-customer-review.md`, `02-visual-design-review.md`, `03-shop-manager-review.md`

---

## Priority Matrix

Issues are grouped by impact. This plan covers **P0 (Critical)** and **P1 (Major)**.

| Priority | Issue | Reviewers |
|----------|-------|-----------|
| P0 | Barcode lookup is O(n) — add `/api/variants/lookup?barcode=X` | Manager, UX |
| P0 | No design system — add tokens, shared Button, base font | Visual |
| P0 | No product prices on listing cards — add `min_price` to list API | UX |
| P0 | No product CRUD in admin — add create/edit forms | Manager |
| P0 | Order lookup fetches all orders — add `/api/orders/lookup?order_number=X` | UX |
| P1 | No loading states anywhere | UX, Visual |
| P1 | No cart badge in nav | UX |
| P1 | No "Set Stock" input in admin | Manager |
| P1 | POS quantity editing + void sale | Manager |
| P1 | Checkout validation + submitting state | UX |
| P1 | Admin product search/filter | Manager |

---

## File Structure

### Backend (new/modified)

```
backend/app/api/products.py          # MODIFY: add barcode lookup, min_price in list
backend/app/schemas/product.py       # MODIFY: add ProductListWithPriceOut
backend/app/api/orders.py            # MODIFY: add order_number lookup
backend/tests/test_products.py       # MODIFY: add barcode lookup test
backend/tests/test_orders.py         # MODIFY: add order_number lookup test
```

### Frontend (new/modified)

```
frontend/packages/shared/src/tokens.ts          # CREATE: design tokens
frontend/packages/shared/src/components/Button.tsx  # CREATE: shared Button
frontend/packages/shared/src/components/Spinner.tsx  # CREATE: loading spinner
frontend/packages/shared/src/index.ts            # MODIFY: re-export new modules
frontend/packages/shared/src/api.ts              # MODIFY: add barcode lookup, order lookup
frontend/packages/shared/src/types.ts            # MODIFY: add ProductListWithPrice

frontend/packages/store/src/App.tsx              # MODIFY: add cart badge, base font, nav styling
frontend/packages/store/src/pages/ShopPage.tsx   # MODIFY: show prices, loading states, category filter
frontend/packages/store/src/pages/CartCheckoutPage.tsx  # MODIFY: validation, submitting state
frontend/packages/store/src/pages/OrderStatusPage.tsx   # MODIFY: use server-side lookup

frontend/packages/admin/src/App.tsx              # MODIFY: base font, nav styling
frontend/packages/admin/src/pages/ProductsInventoryPage.tsx  # MODIFY: search, set-stock input, create/edit product
frontend/packages/admin/src/pages/OrdersPage.tsx # MODIFY: styling fixes

frontend/packages/pos/src/pages/SalePage.tsx     # MODIFY: barcode API, qty editing, void
```

---

## Task 1: Backend — Barcode Lookup Endpoint

**Files:**
- Modify: `backend/app/api/products.py`
- Modify: `backend/tests/test_products.py`

- [ ] **Step 1: Write failing test for barcode lookup**

Add to `backend/tests/test_products.py`:

```python
@pytest.mark.asyncio
async def test_lookup_variant_by_barcode(client):
    await client.post("/api/products", json={
        "title": "Milk", "handle": "milk",
        "variants": [{"title": "1L", "barcode": "8801234000001", "price": "2.99"}],
    })
    response = await client.get("/api/variants/lookup?barcode=8801234000001")
    assert response.status_code == 200
    data = response.json()
    assert data["barcode"] == "8801234000001"
    assert data["price"] == "2.99"
    assert "product_title" in data


@pytest.mark.asyncio
async def test_lookup_variant_by_barcode_not_found(client):
    response = await client.get("/api/variants/lookup?barcode=NONEXISTENT")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_products.py::test_lookup_variant_by_barcode -v`
Expected: FAIL (404)

- [ ] **Step 3: Add VariantLookupOut schema**

Add to `backend/app/schemas/product.py`:

```python
class VariantLookupOut(BaseModel):
    id: int
    product_id: int
    product_title: str
    title: str
    sku: str
    barcode: str
    price: Decimal
    compare_at_price: Decimal | None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Implement barcode lookup endpoint**

Add to `backend/app/api/products.py`:

```python
from app.schemas.product import VariantLookupOut

@router.get("/variants/lookup", response_model=VariantLookupOut)
async def lookup_variant_by_barcode(barcode: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.barcode == barcode)
        .options(selectinload(ProductVariant.product))
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return VariantLookupOut(
        id=variant.id,
        product_id=variant.product_id,
        product_title=variant.product.title,
        title=variant.title,
        sku=variant.sku,
        barcode=variant.barcode,
        price=variant.price,
        compare_at_price=variant.compare_at_price,
    )
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_products.py -v`
Expected: All PASS (including 2 new tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/products.py backend/app/schemas/product.py backend/tests/test_products.py
git commit -m "feat: add barcode lookup endpoint (single API call per scan)"
```

---

## Task 2: Backend — Product List with Min Price + Order Number Lookup

**Files:**
- Modify: `backend/app/api/products.py`
- Modify: `backend/app/api/orders.py`
- Modify: `backend/app/schemas/product.py`
- Modify: `backend/tests/test_products.py`
- Modify: `backend/tests/test_orders.py`

- [ ] **Step 1: Write failing test for product list with price**

Add to `backend/tests/test_products.py`:

```python
@pytest.mark.asyncio
async def test_list_products_includes_min_price(client):
    await client.post("/api/products", json={
        "title": "Milk", "handle": "milk",
        "variants": [
            {"title": "1L", "price": "2.99"},
            {"title": "2L", "price": "4.99"},
        ],
    })
    response = await client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["min_price"] == "2.99"
```

- [ ] **Step 2: Write failing test for order number lookup**

Add to `backend/tests/test_orders.py`:

```python
@pytest.mark.asyncio
async def test_lookup_order_by_number(client, db):
    ids = await seed_for_order(db)
    create = await client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    order_number = create.json()["order_number"]
    response = await client.get(f"/api/orders/lookup?order_number={order_number}")
    assert response.status_code == 200
    assert response.json()["order_number"] == order_number
    assert len(response.json()["line_items"]) == 1


@pytest.mark.asyncio
async def test_lookup_order_not_found(client):
    response = await client.get("/api/orders/lookup?order_number=NOPE")
    assert response.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_products.py::test_list_products_includes_min_price tests/test_orders.py::test_lookup_order_by_number -v`
Expected: FAIL

- [ ] **Step 4: Add ProductListWithPriceOut schema**

Add to `backend/app/schemas/product.py`:

```python
class ProductListWithPriceOut(BaseModel):
    id: int
    title: str
    handle: str
    product_type: str
    status: str
    tags: list[str]
    min_price: Decimal | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Update product list endpoint to include min_price**

Replace the `list_products` function in `backend/app/api/products.py`:

```python
from sqlalchemy import func as sqlfunc
from app.schemas.product import ProductListWithPriceOut

@router.get("/products", response_model=list[ProductListWithPriceOut])
async def list_products(
    status: str | None = None,
    search: str | None = None,
    product_type: str | None = None,
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
    result = await db.execute(query.order_by(Product.id))
    rows = result.all()
    return [
        ProductListWithPriceOut(
            id=r.id, title=r.title, handle=r.handle,
            product_type=r.product_type, status=r.status,
            tags=r.tags, min_price=r.min_price,
        )
        for r in rows
    ]
```

- [ ] **Step 6: Add order number lookup endpoint**

Add to `backend/app/api/orders.py`:

```python
@router.get("/orders/lookup", response_model=OrderOut)
async def lookup_order(order_number: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .where(Order.order_number == order_number)
        .options(selectinload(Order.line_items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
```

Add the missing import at the top of orders.py if not present:
```python
from sqlalchemy.orm import selectinload
```

- [ ] **Step 7: Run all tests**

Run: `cd backend && python -m pytest -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/products.py backend/app/api/orders.py backend/app/schemas/product.py backend/tests/test_products.py backend/tests/test_orders.py
git commit -m "feat: add min_price to product list, product_type filter, order number lookup"
```

---

## Task 3: Frontend — Design Tokens + Shared Components

**Files:**
- Create: `frontend/packages/shared/src/tokens.ts`
- Create: `frontend/packages/shared/src/components/Button.tsx`
- Create: `frontend/packages/shared/src/components/Spinner.tsx`
- Modify: `frontend/packages/shared/src/index.ts`

- [ ] **Step 1: Create design tokens**

Create `frontend/packages/shared/src/tokens.ts`:

```typescript
export const colors = {
  brand: "#5B47E0",
  brandHover: "#4A38C9",
  brandLight: "#EDE9FC",
  surface: "#FFFFFF",
  surfaceMuted: "#F7F7F8",
  border: "#E5E5E7",
  borderStrong: "#C7C7CC",
  textPrimary: "#1A1A1A",
  textSecondary: "#6B6B6B",
  textDisabled: "#ADADAD",
  danger: "#D93025",
  dangerSurface: "#FEF2F2",
  success: "#1A7F37",
  successSurface: "#F0FFF4",
  warning: "#B45309",
  warningSurface: "#FFFBEB",
};

export const spacing = {
  xs: "4px",
  sm: "8px",
  md: "16px",
  lg: "24px",
  xl: "40px",
};

export const radius = {
  sm: "6px",
  md: "10px",
  lg: "16px",
};

export const font = {
  body: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif",
  mono: "'SF Mono', 'Fira Code', monospace",
};

export const shadow = {
  sm: "0 1px 2px rgba(0,0,0,0.05)",
  md: "0 2px 8px rgba(0,0,0,0.08)",
  lg: "0 4px 16px rgba(0,0,0,0.12)",
};

export const navHeight = "56px";

export const baseStyles: Record<string, React.CSSProperties> = {
  page: {
    fontFamily: font.body,
    color: colors.textPrimary,
    minHeight: "100vh",
    background: colors.surfaceMuted,
  },
  nav: {
    padding: `0 ${spacing.lg}`,
    height: navHeight,
    borderBottom: `1px solid ${colors.border}`,
    display: "flex",
    gap: spacing.lg,
    alignItems: "center",
    background: colors.surface,
    position: "sticky" as const,
    top: 0,
    zIndex: 100,
    fontFamily: font.body,
  },
  navBrand: {
    fontWeight: 700,
    fontSize: "1.1rem",
    textDecoration: "none",
    color: colors.brand,
  },
  navLink: {
    textDecoration: "none",
    color: colors.textSecondary,
    fontSize: "0.9rem",
    fontWeight: 500,
  },
  card: {
    background: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    padding: spacing.lg,
  },
  input: {
    padding: "8px 12px",
    border: `1px solid ${colors.borderStrong}`,
    borderRadius: radius.sm,
    fontSize: "14px",
    fontFamily: font.body,
    outline: "none",
    width: "100%",
    boxSizing: "border-box" as const,
  },
  container: {
    maxWidth: 1200,
    margin: "0 auto",
    padding: spacing.lg,
  },
};
```

- [ ] **Step 2: Create shared Button component**

Create `frontend/packages/shared/src/components/Button.tsx`:

```tsx
import { CSSProperties, ButtonHTMLAttributes } from "react";
import { colors, radius, font } from "../tokens";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  fullWidth?: boolean;
  loading?: boolean;
}

const variantStyles: Record<ButtonVariant, CSSProperties> = {
  primary: {
    background: colors.brand,
    color: "#FFFFFF",
    border: "none",
  },
  secondary: {
    background: colors.surfaceMuted,
    color: colors.textPrimary,
    border: `1px solid ${colors.borderStrong}`,
  },
  danger: {
    background: colors.dangerSurface,
    color: colors.danger,
    border: `1px solid ${colors.danger}`,
  },
  ghost: {
    background: "transparent",
    color: colors.textSecondary,
    border: "1px solid transparent",
  },
};

const sizeStyles: Record<string, CSSProperties> = {
  sm: { padding: "4px 10px", fontSize: "13px" },
  md: { padding: "7px 14px", fontSize: "14px" },
  lg: { padding: "10px 20px", fontSize: "15px" },
};

export function Button({
  variant = "secondary",
  size = "md",
  fullWidth = false,
  loading = false,
  disabled,
  style,
  children,
  ...props
}: ButtonProps) {
  const baseStyle: CSSProperties = {
    borderRadius: radius.sm,
    fontFamily: font.body,
    fontWeight: 500,
    cursor: disabled || loading ? "not-allowed" : "pointer",
    opacity: disabled || loading ? 0.6 : 1,
    transition: "all 0.15s ease",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "6px",
    width: fullWidth ? "100%" : undefined,
    ...variantStyles[variant],
    ...sizeStyles[size],
    ...style,
  };

  return (
    <button style={baseStyle} disabled={disabled || loading} {...props}>
      {loading ? "..." : children}
    </button>
  );
}
```

- [ ] **Step 3: Create Spinner component**

Create `frontend/packages/shared/src/components/Spinner.tsx`:

```tsx
import { colors } from "../tokens";

export function Spinner({ size = 24, label }: { size?: number; label?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", padding: "40px 0" }}>
      <div
        style={{
          width: size,
          height: size,
          border: `3px solid ${colors.border}`,
          borderTopColor: colors.brand,
          borderRadius: "50%",
          animation: "spin 0.6s linear infinite",
        }}
      />
      {label && <span style={{ color: colors.textSecondary, fontSize: "14px" }}>{label}</span>}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
```

- [ ] **Step 4: Update barrel export**

Replace `frontend/packages/shared/src/index.ts`:

```typescript
export { api } from "./api";
export { useWebSocket } from "./useWebSocket";
export { Button } from "./components/Button";
export { Spinner } from "./components/Spinner";
export { colors, spacing, radius, font, shadow, navHeight, baseStyles } from "./tokens";
export type * from "./types";
```

- [ ] **Step 5: Verify build**

Run: `cd frontend && pnpm --filter @openmarket/shared build` (or just verify TypeScript compiles)
Actually shared has no build step — verify store builds: `cd frontend && pnpm --filter @openmarket/store build`

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/shared/
git commit -m "feat: add design tokens, shared Button and Spinner components"
```

---

## Task 4: Frontend — Update Shared API Client + Types

**Files:**
- Modify: `frontend/packages/shared/src/api.ts`
- Modify: `frontend/packages/shared/src/types.ts`

- [ ] **Step 1: Update types.ts**

Add to `frontend/packages/shared/src/types.ts`:

```typescript
export interface ProductListWithPrice {
  id: number;
  title: string;
  handle: string;
  product_type: string;
  status: string;
  tags: string[];
  min_price: string | null;
}

export interface VariantLookup {
  id: number;
  product_id: number;
  product_title: string;
  title: string;
  sku: string;
  barcode: string;
  price: string;
  compare_at_price: string | null;
}
```

- [ ] **Step 2: Update api.ts**

Update the `products` namespace in `frontend/packages/shared/src/api.ts`:

```typescript
  products: {
    list: (params?: { status?: string; search?: string; product_type?: string }) => {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null)) as Record<string, string>
      ).toString();
      return request<import("./types").ProductListWithPrice[]>(`/products${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => request<import("./types").Product>(`/products/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Product>("/products", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Product>(`/products/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    archive: (id: number) =>
      request<import("./types").Product>(`/products/${id}`, { method: "DELETE" }),
  },
```

Add `variants` namespace:

```typescript
  variants: {
    lookup: (barcode: string) =>
      request<import("./types").VariantLookup>(`/variants/lookup?barcode=${encodeURIComponent(barcode)}`),
  },
```

Update the `orders` namespace:

```typescript
  orders: {
    list: (params?: { source?: string; fulfillment_status?: string }) => {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null)) as Record<string, string>
      ).toString();
      return request<import("./types").OrderListItem[]>(`/orders${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => request<import("./types").Order>(`/orders/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Order>("/orders", { method: "POST", body: JSON.stringify(data) }),
    lookup: (orderNumber: string) =>
      request<import("./types").Order>(`/orders/lookup?order_number=${encodeURIComponent(orderNumber)}`),
  },
```

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/shared/src/api.ts frontend/packages/shared/src/types.ts
git commit -m "feat: add barcode lookup, order lookup, product_type filter to API client"
```

---

## Task 5: Store — Redesign ShopPage with Prices, Categories, Loading

**Files:**
- Modify: `frontend/packages/store/src/pages/ShopPage.tsx`
- Modify: `frontend/packages/store/src/App.tsx`

- [ ] **Step 1: Rewrite App.tsx with design tokens and cart badge**

Replace `frontend/packages/store/src/App.tsx`:

```tsx
import { Routes, Route, Link } from "react-router-dom";
import { ShopPage } from "./pages/ShopPage";
import { CartCheckoutPage } from "./pages/CartCheckoutPage";
import { OrderStatusPage } from "./pages/OrderStatusPage";
import { CartProvider, useCart } from "./store/cartStore";
import { baseStyles, colors } from "@openmarket/shared";

function NavBar() {
  const { items } = useCart();
  const count = items.reduce((s, i) => s + i.quantity, 0);
  return (
    <nav style={baseStyles.nav}>
      <Link to="/" style={baseStyles.navBrand}>OpenMarket</Link>
      <div style={{ flex: 1 }} />
      <Link to="/" style={baseStyles.navLink}>Shop</Link>
      <Link to="/cart" style={{ ...baseStyles.navLink, position: "relative" as const }}>
        Cart
        {count > 0 && (
          <span style={{
            position: "absolute", top: -8, right: -14,
            background: colors.brand, color: "#fff",
            borderRadius: "50%", width: 18, height: 18,
            fontSize: 11, fontWeight: 700,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>{count}</span>
        )}
      </Link>
      <Link to="/order-status" style={baseStyles.navLink}>Track Order</Link>
    </nav>
  );
}

export function App() {
  return (
    <CartProvider>
      <div style={baseStyles.page}>
        <NavBar />
        <Routes>
          <Route path="/" element={<ShopPage />} />
          <Route path="/cart" element={<CartCheckoutPage />} />
          <Route path="/order-status" element={<OrderStatusPage />} />
        </Routes>
      </div>
    </CartProvider>
  );
}
```

- [ ] **Step 2: Rewrite ShopPage with prices, categories, loading**

Replace `frontend/packages/store/src/pages/ShopPage.tsx`:

```tsx
import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket, Spinner, Button, colors, baseStyles, spacing, radius, shadow } from "@openmarket/shared";
import type { Product, ProductListWithPrice } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

export function ShopPage() {
  const [products, setProducts] = useState<ProductListWithPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const { addItem } = useCart();

  const productTypes = [...new Set(products.map((p) => p.product_type).filter(Boolean))].sort();

  useEffect(() => {
    setLoading(true);
    api.products.list({
      status: "active",
      search: search || undefined,
      product_type: selectedType || undefined,
    })
      .then(setProducts)
      .finally(() => setLoading(false));
  }, [search, selectedType]);

  const handleInventoryUpdate = useCallback(() => {}, []);
  useWebSocket(handleInventoryUpdate);

  const openProduct = async (id: number) => {
    setDetailLoading(true);
    const product = await api.products.get(id);
    setSelectedProduct(product);
    setDetailLoading(false);
  };

  return (
    <div style={{ ...baseStyles.container, display: "flex", gap: spacing.lg }}>
      {/* Sidebar: Category Filter */}
      <div style={{ width: 180, flexShrink: 0 }}>
        <h3 style={{ fontSize: "14px", color: colors.textSecondary, marginBottom: spacing.sm, textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Categories
        </h3>
        <div
          onClick={() => setSelectedType(null)}
          style={{
            padding: "6px 10px", cursor: "pointer", borderRadius: radius.sm,
            fontSize: "14px", marginBottom: "2px",
            background: selectedType === null ? colors.brandLight : "transparent",
            color: selectedType === null ? colors.brand : colors.textPrimary,
            fontWeight: selectedType === null ? 600 : 400,
          }}
        >All Products</div>
        {productTypes.map((t) => (
          <div
            key={t}
            onClick={() => setSelectedType(t)}
            style={{
              padding: "6px 10px", cursor: "pointer", borderRadius: radius.sm,
              fontSize: "14px", marginBottom: "2px", textTransform: "capitalize",
              background: selectedType === t ? colors.brandLight : "transparent",
              color: selectedType === t ? colors.brand : colors.textPrimary,
              fontWeight: selectedType === t ? 600 : 400,
            }}
          >{t}</div>
        ))}
      </div>

      {/* Main Content */}
      <div style={{ flex: 1 }}>
        <input
          type="text"
          placeholder="Search products..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ ...baseStyles.input, marginBottom: spacing.lg }}
        />

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
              <div
                key={p.id}
                onClick={() => openProduct(p.id)}
                style={{
                  ...baseStyles.card,
                  cursor: "pointer",
                  transition: "box-shadow 0.15s, border-color 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = shadow.md;
                  e.currentTarget.style.borderColor = colors.borderStrong;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = "none";
                  e.currentTarget.style.borderColor = colors.border;
                }}
              >
                <div style={{ fontSize: "12px", color: colors.textSecondary, textTransform: "capitalize", marginBottom: "4px" }}>
                  {p.product_type}
                </div>
                <h3 style={{ margin: "0 0 8px", fontSize: "15px", fontWeight: 600 }}>{p.title}</h3>
                {p.min_price && (
                  <div style={{ fontSize: "16px", fontWeight: 700, color: colors.brand }}>
                    ${p.min_price}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Product Detail Side Panel */}
      {(selectedProduct || detailLoading) && (
        <div style={{ width: 320, flexShrink: 0, ...baseStyles.card, alignSelf: "flex-start", position: "sticky" as const, top: `calc(${spacing.lg} + 56px)` }}>
          {detailLoading ? (
            <Spinner label="Loading..." />
          ) : selectedProduct && (
            <>
              <h2 style={{ margin: "0 0 4px", fontSize: "18px" }}>{selectedProduct.title}</h2>
              {selectedProduct.description && (
                <p style={{ color: colors.textSecondary, fontSize: "14px", margin: "0 0 16px" }}>{selectedProduct.description}</p>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {selectedProduct.variants.map((v) => (
                  <div key={v.id} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "8px", background: colors.surfaceMuted, borderRadius: radius.sm,
                  }}>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: "14px" }}>{v.title}</div>
                      <div style={{ fontSize: "15px", fontWeight: 700, color: colors.brand }}>${v.price}</div>
                    </div>
                    <Button variant="primary" size="sm" onClick={() => addItem(selectedProduct, v)}>
                      Add
                    </Button>
                  </div>
                ))}
              </div>
              <Button variant="ghost" size="sm" onClick={() => setSelectedProduct(null)} style={{ marginTop: "12px", width: "100%" }}>
                Close
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm --filter @openmarket/store build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/store/src/
git commit -m "feat: redesign store with prices, categories, loading states, cart badge"
```

---

## Task 6: Store — Fix CartCheckoutPage and OrderStatusPage

**Files:**
- Modify: `frontend/packages/store/src/pages/CartCheckoutPage.tsx`
- Modify: `frontend/packages/store/src/pages/OrderStatusPage.tsx`

- [ ] **Step 1: Rewrite CartCheckoutPage with validation + submitting state**

Replace `frontend/packages/store/src/pages/CartCheckoutPage.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Button, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

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
  const [submitting, setSubmitting] = useState(false);
  const [orderNumber, setOrderNumber] = useState("");

  const applyDiscount = async () => {
    try {
      const d = await api.discounts.lookup(discountCode);
      setDiscount({ type: d.discount_type, value: parseFloat(d.value) });
      setError("");
    } catch {
      setError("Invalid or expired discount code");
      setDiscount(null);
    }
  };

  const finalTotal = discount
    ? discount.type === "percentage" ? total * (1 - discount.value / 100) : Math.max(0, total - discount.value)
    : total;

  const canSubmit = name && phone && address && city && zip && items.length > 0 && !submitting;

  const placeOrder = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError("");
    try {
      const order = await api.orders.create({
        source: "web",
        customer_name: name, customer_phone: phone,
        shipping_address: { address1: address, city, zip },
        line_items: items.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
      });
      setOrderNumber(order.order_number);
      clearCart();
    } catch (e: any) {
      setError(e.message || "Failed to place order");
    } finally {
      setSubmitting(false);
    }
  };

  if (orderNumber) {
    return (
      <div style={{ ...baseStyles.container, maxWidth: 500, textAlign: "center", paddingTop: spacing.xl }}>
        <div style={{ ...baseStyles.card }}>
          <div style={{ fontSize: "40px", marginBottom: spacing.md }}>&#10003;</div>
          <h2 style={{ margin: "0 0 8px" }}>Order Placed!</h2>
          <p style={{ color: colors.textSecondary }}>Your order number is:</p>
          <p style={{ fontSize: "20px", fontWeight: 700, color: colors.brand, margin: "8px 0 24px" }}>{orderNumber}</p>
          <p style={{ color: colors.textSecondary, fontSize: "14px", marginBottom: spacing.lg }}>
            Payment will be collected on delivery.
          </p>
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
                padding: "12px 0",
                borderBottom: i < items.length - 1 ? `1px solid ${colors.border}` : undefined,
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.product.title}</div>
                  <div style={{ color: colors.textSecondary, fontSize: "13px" }}>{item.variant.title} &middot; ${item.variant.price}</div>
                </div>
                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <Button variant="secondary" size="sm" onClick={() => updateQuantity(item.variant.id, item.quantity - 1)}>-</Button>
                  <span style={{ width: 28, textAlign: "center", fontWeight: 600 }}>{item.quantity}</span>
                  <Button variant="secondary" size="sm" onClick={() => updateQuantity(item.variant.id, item.quantity + 1)}>+</Button>
                  <Button variant="danger" size="sm" onClick={() => removeItem(item.variant.id)}>Remove</Button>
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
            <div style={{ fontSize: "20px", fontWeight: 700, textAlign: "right", marginTop: spacing.md }}>
              Total: ${finalTotal.toFixed(2)}
            </div>
          </div>

          <div style={{ ...baseStyles.card }}>
            <h3 style={{ margin: "0 0 16px", fontSize: "16px" }}>Delivery Details</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <input placeholder="Full name *" value={name} onChange={(e) => setName(e.target.value)} style={baseStyles.input} />
              <input placeholder="Phone *" value={phone} onChange={(e) => setPhone(e.target.value)} style={baseStyles.input} />
              <input placeholder="Address *" value={address} onChange={(e) => setAddress(e.target.value)} style={baseStyles.input} />
              <div style={{ display: "flex", gap: "10px" }}>
                <input placeholder="City *" value={city} onChange={(e) => setCity(e.target.value)} style={baseStyles.input} />
                <input placeholder="ZIP *" value={zip} onChange={(e) => setZip(e.target.value)} style={{ ...baseStyles.input, maxWidth: 120 }} />
              </div>
            </div>
            <p style={{ color: colors.textSecondary, fontSize: "13px", margin: "12px 0 4px" }}>
              Payment will be collected on delivery.
            </p>
            {error && (
              <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px", marginTop: "8px" }}>
                {error}
              </div>
            )}
            <Button variant="primary" size="lg" fullWidth loading={submitting} disabled={!canSubmit} onClick={placeOrder} style={{ marginTop: spacing.md }}>
              Place Order — ${finalTotal.toFixed(2)}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Rewrite OrderStatusPage with server-side lookup**

Replace `frontend/packages/store/src/pages/OrderStatusPage.tsx`:

```tsx
import { useState } from "react";
import { api, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Order } from "@openmarket/shared";

export function OrderStatusPage() {
  const [orderNumber, setOrderNumber] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const lookup = async () => {
    if (!orderNumber.trim()) return;
    setLoading(true);
    setError("");
    setOrder(null);
    try {
      const found = await api.orders.lookup(orderNumber.trim());
      setOrder(found);
    } catch {
      setError("Order not found. Please check the order number and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ ...baseStyles.container, maxWidth: 600 }}>
      <h2 style={{ marginBottom: spacing.lg }}>Track Your Order</h2>
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <div style={{ display: "flex", gap: "8px" }}>
          <input
            placeholder="Enter order number (e.g. ORD-...)"
            value={orderNumber}
            onChange={(e) => setOrderNumber(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && lookup()}
            style={baseStyles.input}
          />
          <Button variant="primary" onClick={lookup} loading={loading} style={{ flexShrink: 0 }}>
            Look Up
          </Button>
        </div>
        {error && (
          <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px", marginTop: "10px" }}>
            {error}
          </div>
        )}
      </div>

      {loading && <Spinner label="Looking up order..." />}

      {order && (
        <div style={baseStyles.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
            <h3 style={{ margin: 0, fontSize: "16px" }}>Order {order.order_number}</h3>
            <span style={{
              padding: "4px 10px", borderRadius: radius.sm, fontSize: "12px", fontWeight: 600, textTransform: "uppercase",
              background: order.fulfillment_status === "fulfilled" ? colors.successSurface : colors.warningSurface,
              color: order.fulfillment_status === "fulfilled" ? colors.success : colors.warning,
            }}>
              {order.fulfillment_status}
            </span>
          </div>
          <div style={{ fontSize: "14px", color: colors.textSecondary, marginBottom: spacing.md }}>
            Placed {new Date(order.created_at).toLocaleString()}
          </div>
          <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: spacing.md }}>
            {order.line_items.map((li) => (
              <div key={li.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: "14px" }}>
                <span>{li.title} &times; {li.quantity}</span>
                <span style={{ fontWeight: 600 }}>${(parseFloat(li.price) * li.quantity).toFixed(2)}</span>
              </div>
            ))}
            <div style={{ display: "flex", justifyContent: "space-between", borderTop: `1px solid ${colors.border}`, paddingTop: "8px", marginTop: "8px", fontWeight: 700 }}>
              <span>Total</span>
              <span>${order.total_price}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm --filter @openmarket/store build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/store/src/
git commit -m "feat: fix checkout validation, add submitting state, server-side order lookup"
```

---

## Task 7: Admin — Search, Set-Stock, Product CRUD, Styling

**Files:**
- Modify: `frontend/packages/admin/src/App.tsx`
- Modify: `frontend/packages/admin/src/pages/ProductsInventoryPage.tsx`
- Modify: `frontend/packages/admin/src/pages/OrdersPage.tsx`

- [ ] **Step 1: Rewrite Admin App.tsx with design tokens**

Replace `frontend/packages/admin/src/App.tsx`:

```tsx
import { Routes, Route, Link, Navigate, useLocation } from "react-router-dom";
import { ProductsInventoryPage } from "./pages/ProductsInventoryPage";
import { OrdersPage } from "./pages/OrdersPage";
import { baseStyles, colors } from "@openmarket/shared";

export function App() {
  const location = useLocation();
  const linkStyle = (path: string) => ({
    ...baseStyles.navLink,
    color: location.pathname === path ? colors.brand : colors.textSecondary,
    fontWeight: location.pathname === path ? 600 : 500,
  });

  return (
    <div style={baseStyles.page}>
      <nav style={baseStyles.nav}>
        <span style={{ ...baseStyles.navBrand, cursor: "default" }}>OpenMarket Admin</span>
        <div style={{ flex: 1 }} />
        <Link to="/products" style={linkStyle("/products")}>Products & Inventory</Link>
        <Link to="/orders" style={linkStyle("/orders")}>Orders</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/products" replace />} />
        <Route path="/products" element={<ProductsInventoryPage />} />
        <Route path="/orders" element={<OrdersPage />} />
      </Routes>
    </div>
  );
}
```

- [ ] **Step 2: Rewrite ProductsInventoryPage with search, set-stock, create product**

Replace `frontend/packages/admin/src/pages/ProductsInventoryPage.tsx`:

```tsx
import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Product, ProductListWithPrice, InventoryLevel } from "@openmarket/shared";

export function ProductsInventoryPage() {
  const [products, setProducts] = useState<ProductListWithPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [inventory, setInventory] = useState<Record<number, InventoryLevel>>({});
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedProduct, setExpandedProduct] = useState<Product | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newHandle, setNewHandle] = useState("");
  const [newType, setNewType] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [newBarcode, setNewBarcode] = useState("");
  const [stockInputs, setStockInputs] = useState<Record<number, string>>({});

  const loadProducts = async () => {
    setLoading(true);
    const prods = await api.products.list({ search: search || undefined });
    setProducts(prods);
    setLoading(false);
  };

  const loadInventory = async () => {
    const levels = await api.inventory.levels(1);
    const map: Record<number, InventoryLevel> = {};
    for (const l of levels) map[l.inventory_item_id] = l;
    setInventory(map);
  };

  useEffect(() => { loadProducts(); loadInventory(); }, [search]);

  const handleInventoryUpdate = useCallback((update: { inventory_item_id: number; available: number; location_id: number }) => {
    setInventory((prev) => ({
      ...prev,
      [update.inventory_item_id]: { ...prev[update.inventory_item_id], available: update.available },
    }));
  }, []);
  useWebSocket(handleInventoryUpdate);

  const expand = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); setExpandedProduct(null); return; }
    setExpandedId(id);
    setExpandedProduct(await api.products.get(id));
  };

  const adjustStock = async (inventoryItemId: number, delta: number) => {
    await api.inventory.adjust({ inventory_item_id: inventoryItemId, location_id: 1, available_adjustment: delta });
    await loadInventory();
  };

  const setStock = async (inventoryItemId: number) => {
    const val = parseInt(stockInputs[inventoryItemId] || "");
    if (isNaN(val) || val < 0) return;
    await api.inventory.set({ inventory_item_id: inventoryItemId, location_id: 1, available: val });
    setStockInputs((p) => ({ ...p, [inventoryItemId]: "" }));
    await loadInventory();
  };

  const createProduct = async () => {
    if (!newTitle || !newHandle || !newPrice) return;
    await api.products.create({
      title: newTitle, handle: newHandle, product_type: newType,
      variants: [{ title: "Default", price: newPrice, barcode: newBarcode }],
    });
    setNewTitle(""); setNewHandle(""); setNewType(""); setNewPrice(""); setNewBarcode("");
    setShowCreate(false);
    loadProducts(); loadInventory();
  };

  return (
    <div style={baseStyles.container}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
        <h2 style={{ margin: 0 }}>Products & Inventory</h2>
        <Button variant="primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "Cancel" : "+ Add Product"}
        </Button>
      </div>

      {showCreate && (
        <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
          <h3 style={{ margin: "0 0 12px", fontSize: "15px" }}>New Product</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <input placeholder="Title *" value={newTitle} onChange={(e) => { setNewTitle(e.target.value); setNewHandle(e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")); }} style={baseStyles.input} />
            <input placeholder="Handle" value={newHandle} onChange={(e) => setNewHandle(e.target.value)} style={baseStyles.input} />
            <input placeholder="Type (e.g. dairy)" value={newType} onChange={(e) => setNewType(e.target.value)} style={baseStyles.input} />
            <input placeholder="Price *" value={newPrice} onChange={(e) => setNewPrice(e.target.value)} style={baseStyles.input} />
            <input placeholder="Barcode" value={newBarcode} onChange={(e) => setNewBarcode(e.target.value)} style={baseStyles.input} />
          </div>
          <Button variant="primary" onClick={createProduct} disabled={!newTitle || !newPrice} style={{ marginTop: "12px" }}>
            Create Product
          </Button>
        </div>
      )}

      <input placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ ...baseStyles.input, marginBottom: spacing.lg }} />

      {loading ? <Spinner label="Loading products..." /> : (
        <div style={{ ...baseStyles.card, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
            <thead>
              <tr style={{ background: colors.surfaceMuted, textAlign: "left" }}>
                <th style={{ padding: "10px 16px" }}>Title</th>
                <th style={{ padding: "10px 16px" }}>Type</th>
                <th style={{ padding: "10px 16px" }}>Price</th>
                <th style={{ padding: "10px 16px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <>
                  <tr key={p.id} onClick={() => expand(p.id)} style={{ cursor: "pointer", borderBottom: `1px solid ${colors.border}`, background: expandedId === p.id ? colors.surfaceMuted : colors.surface }}>
                    <td style={{ padding: "10px 16px", fontWeight: 500 }}>{p.title}</td>
                    <td style={{ padding: "10px 16px", textTransform: "capitalize", color: colors.textSecondary }}>{p.product_type}</td>
                    <td style={{ padding: "10px 16px" }}>{p.min_price ? `$${p.min_price}` : "—"}</td>
                    <td style={{ padding: "10px 16px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: "4px", fontSize: "12px", fontWeight: 600,
                        background: p.status === "active" ? colors.successSurface : colors.surfaceMuted,
                        color: p.status === "active" ? colors.success : colors.textSecondary,
                      }}>{p.status}</span>
                    </td>
                  </tr>
                  {expandedId === p.id && expandedProduct && (
                    <tr key={`${p.id}-detail`}>
                      <td colSpan={4} style={{ padding: "16px", background: colors.surfaceMuted, borderBottom: `1px solid ${colors.border}` }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                          <thead>
                            <tr style={{ textAlign: "left", color: colors.textSecondary }}>
                              <th style={{ padding: "6px 0" }}>Variant</th><th>SKU</th><th>Barcode</th><th>Price</th><th>Stock</th><th>Set Stock</th><th>Adjust</th>
                            </tr>
                          </thead>
                          <tbody>
                            {expandedProduct.variants.map((v) => {
                              const level = Object.values(inventory).find((l) => l.inventory_item_id === v.id) || null;
                              const stock = level?.available ?? "—";
                              const isLow = level != null && level.available <= level.low_stock_threshold;
                              return (
                                <tr key={v.id} style={{ borderTop: `1px solid ${colors.border}` }}>
                                  <td style={{ padding: "8px 0" }}>{v.title}</td>
                                  <td style={{ color: colors.textSecondary }}>{v.sku || "—"}</td>
                                  <td style={{ fontFamily: "monospace", fontSize: "12px" }}>{v.barcode || "—"}</td>
                                  <td>${v.price}</td>
                                  <td style={{ color: isLow ? colors.danger : colors.textPrimary, fontWeight: isLow ? 700 : 400 }}>
                                    {stock} {isLow && <span style={{ fontSize: "11px" }}>LOW</span>}
                                  </td>
                                  <td>
                                    {level && (
                                      <div style={{ display: "flex", gap: "4px" }}>
                                        <input
                                          placeholder="qty"
                                          value={stockInputs[level.inventory_item_id] || ""}
                                          onChange={(e) => setStockInputs((p) => ({ ...p, [level.inventory_item_id]: e.target.value }))}
                                          onKeyDown={(e) => e.key === "Enter" && setStock(level.inventory_item_id)}
                                          style={{ ...baseStyles.input, width: 60, padding: "4px 6px", fontSize: "12px" }}
                                        />
                                        <Button variant="secondary" size="sm" onClick={() => setStock(level.inventory_item_id)}>Set</Button>
                                      </div>
                                    )}
                                  </td>
                                  <td>
                                    {level && (
                                      <div style={{ display: "flex", gap: "4px" }}>
                                        <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, -1); }}>-1</Button>
                                        <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, 1); }}>+1</Button>
                                        <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, 10); }}>+10</Button>
                                      </div>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Rewrite OrdersPage with design tokens**

Replace `frontend/packages/admin/src/pages/OrdersPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Order, OrderListItem } from "@openmarket/shared";

export function OrdersPage() {
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"unfulfilled" | "fulfilled">("unfulfilled");
  const [expandedOrder, setExpandedOrder] = useState<Order | null>(null);

  const loadOrders = async () => {
    setLoading(true);
    setOrders(await api.orders.list({ fulfillment_status: tab }));
    setLoading(false);
  };

  useEffect(() => { loadOrders(); }, [tab]);

  const expandOrder = async (id: number) => {
    if (expandedOrder?.id === id) { setExpandedOrder(null); return; }
    setExpandedOrder(await api.orders.get(id));
  };

  const fulfill = async (orderId: number) => {
    await api.fulfillments.create(orderId, { status: "delivered" });
    await loadOrders();
    setExpandedOrder(null);
  };

  const tabStyle = (active: boolean) => ({
    padding: "7px 16px", borderRadius: radius.sm, fontSize: "14px", fontWeight: active ? 600 : 400,
    background: active ? colors.brand : "transparent",
    color: active ? "#fff" : colors.textPrimary,
    border: `1px solid ${active ? colors.brand : colors.borderStrong}`,
    cursor: "pointer" as const,
  });

  return (
    <div style={baseStyles.container}>
      <h2 style={{ marginBottom: spacing.lg }}>Orders</h2>
      <div style={{ display: "flex", gap: "8px", marginBottom: spacing.lg }}>
        <button onClick={() => setTab("unfulfilled")} style={tabStyle(tab === "unfulfilled")}>Unfulfilled</button>
        <button onClick={() => setTab("fulfilled")} style={tabStyle(tab === "fulfilled")}>Fulfilled</button>
      </div>

      {loading ? <Spinner label="Loading orders..." /> : orders.length === 0 ? (
        <div style={{ ...baseStyles.card, textAlign: "center", padding: spacing.xl, color: colors.textSecondary }}>
          No {tab} orders
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
                <>
                  <tr key={o.id} onClick={() => expandOrder(o.id)} style={{ cursor: "pointer", borderBottom: `1px solid ${colors.border}`, background: expandedOrder?.id === o.id ? colors.surfaceMuted : colors.surface }}>
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
                    <tr key={`${o.id}-detail`}>
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
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && pnpm --filter @openmarket/admin build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/admin/src/
git commit -m "feat: redesign admin with search, set-stock, product creation, design tokens"
```

---

## Task 8: POS — Barcode API, Quantity Editing, Void Sale

**Files:**
- Modify: `frontend/packages/pos/src/pages/SalePage.tsx`
- Modify: `frontend/packages/pos/src/App.tsx`

- [ ] **Step 1: Update POS App.tsx with design tokens**

Replace `frontend/packages/pos/src/App.tsx`:

```tsx
import { SalePage } from "./pages/SalePage";
import { font } from "@openmarket/shared";

export function App() {
  return <div style={{ fontFamily: font.body }}><SalePage /></div>;
}
```

- [ ] **Step 2: Rewrite SalePage with barcode API, quantity edit, void**

Replace `frontend/packages/pos/src/pages/SalePage.tsx`:

```tsx
import { useState, useRef, useEffect, useCallback } from "react";
import { api, useWebSocket, Button, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Product, ProductVariant } from "@openmarket/shared";

interface SaleItem { variant: ProductVariant; productTitle: string; quantity: number; }

export function SalePage() {
  const [barcodeInput, setBarcodeInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [saleItems, setSaleItems] = useState<SaleItem[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const barcodeRef = useRef<HTMLInputElement>(null);

  useEffect(() => { barcodeRef.current?.focus(); }, []);
  useEffect(() => {
    if (success) { const t = setTimeout(() => { setSuccess(""); barcodeRef.current?.focus(); }, 3000); return () => clearTimeout(t); }
  }, [success]);

  const handleInventoryUpdate = useCallback(() => {}, []);
  useWebSocket(handleInventoryUpdate);

  const addByBarcode = async (barcode: string) => {
    setError("");
    try {
      const result = await api.variants.lookup(barcode);
      addToSale(result.product_title, {
        id: result.id, product_id: result.product_id, title: result.title,
        sku: result.sku, barcode: result.barcode, price: result.price,
        compare_at_price: result.compare_at_price, position: 0,
      });
      setBarcodeInput("");
    } catch {
      setError(`No product found with barcode: ${barcode}`);
    }
  };

  const searchProducts = async (query: string) => {
    if (!query) { setSearchResults([]); return; }
    const products = await api.products.list({ status: "active", search: query });
    const full = await Promise.all(products.slice(0, 5).map((p) => api.products.get(p.id)));
    setSearchResults(full);
  };

  const addToSale = (productTitle: string, variant: ProductVariant) => {
    setSaleItems((prev) => {
      const existing = prev.find((i) => i.variant.id === variant.id);
      if (existing) return prev.map((i) => i.variant.id === variant.id ? { ...i, quantity: i.quantity + 1 } : i);
      return [...prev, { variant, productTitle, quantity: 1 }];
    });
    setSearchResults([]); setSearchInput(""); barcodeRef.current?.focus();
  };

  const updateQty = (variantId: number, qty: number) => {
    if (qty <= 0) { setSaleItems((prev) => prev.filter((i) => i.variant.id !== variantId)); return; }
    setSaleItems((prev) => prev.map((i) => i.variant.id === variantId ? { ...i, quantity: qty } : i));
  };

  const removeItem = (variantId: number) => setSaleItems((prev) => prev.filter((i) => i.variant.id !== variantId));
  const total = saleItems.reduce((sum, item) => sum + parseFloat(item.variant.price) * item.quantity, 0);

  const voidSale = () => { if (confirm("Void this sale? All items will be cleared.")) { setSaleItems([]); barcodeRef.current?.focus(); } };

  const completeSale = async () => {
    setError("");
    try {
      const order = await api.orders.create({ source: "pos", line_items: saleItems.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })) });
      setSaleItems([]);
      setSuccess(`Sale completed! ${order.order_number}`);
    } catch (e: any) { setError(e.message); }
  };

  const handleBarcodeKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter" && barcodeInput.trim()) addByBarcode(barcodeInput.trim()); };

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* Left: Input Area */}
      <div style={{ flex: 1, padding: spacing.lg, borderRight: `1px solid ${colors.border}`, background: colors.surface, display: "flex", flexDirection: "column" }}>
        <h2 style={{ margin: `0 0 ${spacing.lg}`, color: colors.brand }}>POS</h2>

        <div style={{ marginBottom: spacing.lg }}>
          <label style={{ display: "block", fontWeight: 600, marginBottom: "4px", fontSize: "13px", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: "0.5px" }}>Scan Barcode</label>
          <input ref={barcodeRef} value={barcodeInput} onChange={(e) => setBarcodeInput(e.target.value)} onKeyDown={handleBarcodeKeyDown}
            placeholder="Scan or type barcode..."
            style={{ ...baseStyles.input, padding: "12px", fontSize: "16px" }} />
        </div>

        <div style={{ marginBottom: spacing.lg }}>
          <label style={{ display: "block", fontWeight: 600, marginBottom: "4px", fontSize: "13px", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: "0.5px" }}>Search Product</label>
          <input value={searchInput} onChange={(e) => { setSearchInput(e.target.value); searchProducts(e.target.value); }}
            placeholder="Type to search..."
            style={baseStyles.input} />
          {searchResults.length > 0 && (
            <div style={{ border: `1px solid ${colors.border}`, borderRadius: radius.sm, maxHeight: 200, overflowY: "auto", marginTop: "4px", background: colors.surface }}>
              {searchResults.map((p) => p.variants.map((v) => (
                <div key={v.id} onClick={() => addToSale(p.title, v)}
                  style={{ padding: "10px 12px", cursor: "pointer", borderBottom: `1px solid ${colors.border}`, fontSize: "14px" }}>
                  <strong>{p.title}</strong> — {v.title} <span style={{ color: colors.brand, fontWeight: 600 }}>${v.price}</span>
                </div>
              )))}
            </div>
          )}
        </div>

        {error && <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "10px 14px", borderRadius: radius.sm, fontSize: "14px", marginBottom: spacing.md }}>{error}</div>}
        {success && <div style={{ background: colors.successSurface, color: colors.success, padding: "10px 14px", borderRadius: radius.sm, fontSize: "16px", fontWeight: 600 }}>{success}</div>}
      </div>

      {/* Right: Current Sale */}
      <div style={{ width: 420, padding: spacing.lg, display: "flex", flexDirection: "column", background: colors.surfaceMuted }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
          <h3 style={{ margin: 0 }}>Current Sale</h3>
          {saleItems.length > 0 && <Button variant="danger" size="sm" onClick={voidSale}>Void Sale</Button>}
        </div>

        <div style={{ flex: 1, overflowY: "auto" }}>
          {saleItems.length === 0 ? (
            <div style={{ textAlign: "center", padding: spacing.xl, color: colors.textDisabled }}>No items scanned</div>
          ) : saleItems.map((item) => (
            <div key={item.variant.id} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "10px 12px", marginBottom: "6px",
              background: colors.surface, borderRadius: radius.sm, border: `1px solid ${colors.border}`,
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.productTitle}</div>
                <div style={{ color: colors.textSecondary, fontSize: "13px" }}>{item.variant.title} &middot; ${item.variant.price}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Button variant="secondary" size="sm" onClick={() => updateQty(item.variant.id, item.quantity - 1)}>-</Button>
                <input
                  value={item.quantity}
                  onChange={(e) => { const v = parseInt(e.target.value); if (!isNaN(v)) updateQty(item.variant.id, v); }}
                  style={{ width: 40, textAlign: "center", padding: "4px", border: `1px solid ${colors.borderStrong}`, borderRadius: radius.sm, fontSize: "14px", fontWeight: 600 }}
                />
                <Button variant="secondary" size="sm" onClick={() => updateQty(item.variant.id, item.quantity + 1)}>+</Button>
                <Button variant="ghost" size="sm" onClick={() => removeItem(item.variant.id)} style={{ color: colors.danger }}>&#10005;</Button>
              </div>
            </div>
          ))}
        </div>

        <div style={{ borderTop: `2px solid ${colors.textPrimary}`, paddingTop: spacing.md }}>
          <p style={{ fontSize: "28px", fontWeight: 700, textAlign: "right", margin: `0 0 ${spacing.md}` }}>
            ${total.toFixed(2)}
          </p>
          <Button variant="primary" size="lg" fullWidth disabled={saleItems.length === 0} onClick={completeSale}
            style={{ background: "#1A7F37", padding: "14px", fontSize: "18px" }}>
            Complete Sale
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && pnpm --filter @openmarket/pos build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/pos/src/
git commit -m "feat: POS barcode API lookup, quantity editing, void sale, design tokens"
```

---

## Task 9: Rebuild Frontend & End-to-End Verification

**Files:** None (verification only)

- [ ] **Step 1: Build all frontends**

Run: `cd frontend && pnpm -r build`
Expected: All 3 apps build successfully

- [ ] **Step 2: Restart Docker to pick up new builds**

Run: `docker compose restart nginx`

- [ ] **Step 3: Run full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS (including new barcode + order lookup tests)

- [ ] **Step 4: Test barcode lookup API**

Run: `curl -s "http://localhost:8000/api/variants/lookup?barcode=8801234000001" | python3 -m json.tool`
Expected: Returns variant with product_title

- [ ] **Step 5: Test order number lookup API**

Create an order first, then look it up:
```bash
ORDER=$(curl -s -X POST http://localhost:8000/api/orders -H "Content-Type: application/json" -d '{"source":"pos","line_items":[{"variant_id":1,"quantity":1}]}' | python3 -c "import sys,json; print(json.load(sys.stdin)['order_number'])")
curl -s "http://localhost:8000/api/orders/lookup?order_number=$ORDER" | python3 -m json.tool
```
Expected: Returns full order with line_items

- [ ] **Step 6: Test product list includes min_price**

Run: `curl -s http://localhost:8000/api/products | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].keys())"`
Expected: Contains `min_price` key

- [ ] **Step 7: Verify Nginx serves updated frontends**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost/
curl -s -o /dev/null -w "%{http_code}" http://localhost/admin/
curl -s -o /dev/null -w "%{http_code}" http://localhost/pos/
```
Expected: All return 200

- [ ] **Step 8: Commit any remaining changes**

```bash
git add -A
git commit -m "chore: rebuild all frontends after feedback fixes"
```
