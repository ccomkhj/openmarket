# Admin UX Fixups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three blocking usability findings from the 2026-04-03 shop-manager review (`docs/feedbacks/03-shop-manager-review.md`): (1) the Products page is read-only — a shop manager cannot update a price, barcode, or SKU without database access; (2) the POS barcode scanner does a full product list fetch on every scan (N+1); (3) there's no admin-side view of recent sales with a Storno trigger. All three are independent of the fiscal stack and only need backend + admin-UI changes.

**Architecture:** Two new backend endpoints — `GET /api/variants/lookup?barcode=X` (indexed single-row lookup) and `PUT /api/variants/{id}` (partial update of price/barcode/sku/title/vat_rate). One new admin page (variant edit modal reachable from the Products list). One new admin page (Recent Sales) that lists `PosTransaction`s with a void button calling Plan D's Storno route. The existing POS `SalePage` barcode scanner is migrated from full-list scan to the new `lookup` endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, React + TypeScript. No new dependencies.

**Spec reference:** `docs/feedbacks/03-shop-manager-review.md`.

**Starting point:** `main` after Plans A–D. Plan D adds `ProductVariant.vat_rate` and the Storno endpoint; both are used here.

**Explicitly deferred (not this plan):**

- **Bulk import / CSV upload** — Phase 2.
- **Inline table editing** — a modal is simpler and ships in this plan.
- **Product image upload in the edit flow** — orthogonal; `POST /products/{id}/images` already exists.
- **Returns/refund (non-fiscal-Storno)** — there's an existing `returns` router; out of scope here.

---

## File Structure

**Backend new:**

- `backend/app/api/variants.py` — `GET /api/variants/lookup`, `PUT /api/variants/{id}`
- `backend/alembic/versions/0110_variant_barcode_index.py` — ensure a unique-partial index on `barcode`
- `backend/tests/test_variants_api.py`

**Backend modified:**

- `backend/app/main.py` — register the variants router
- `backend/app/api/orders.py` — new `GET /api/pos-transactions` (recent sales list)
- `backend/app/schemas/product.py` — `VariantUpdate`, `VariantOut`, `VariantLookup` (if not already present — types survey mentions `VariantLookup`)

**Frontend new:**

- `frontend/packages/admin/src/pages/VariantEdit.tsx` — modal
- `frontend/packages/admin/src/pages/RecentSales.tsx`

**Frontend modified:**

- `frontend/packages/shared/src/api.ts` — `variants.lookup`, `variants.update`, `posTransactions.list`
- `frontend/packages/admin/src/pages/Products.tsx` — "Edit" button on each variant row
- `frontend/packages/admin/src/App.tsx` — route + nav for Recent Sales
- `frontend/packages/pos/src/pages/SalePage.tsx` — replace full-list barcode scan with `api.variants.lookup`

---

## Task 1: Barcode index + migration

The existing `ProductVariant.barcode` column is declared `indexed=True` in the model but not enforced as unique. A unique partial index (ignoring NULL) makes the lookup O(log n) and prevents accidental double-assignment of a barcode across variants. If an index already exists under a different name, this migration is a no-op under `IF NOT EXISTS`.

**Files:**
- Create: `backend/alembic/versions/0110_variant_barcode_index.py`

- [ ] **Step 1.1: Check existing indexes**

Run: `cd backend && alembic upgrade head && psql $DATABASE_URL -c "\d product_variants"` (if psql available) OR read the latest `product_variants`-touching migrations to confirm what's indexed.

- [ ] **Step 1.2: Generate + rename**

Run: `cd backend && alembic revision -m "variant barcode unique index"`
Rename to `0110_variant_barcode_index.py`. Set `down_revision = "0109_add_card_auth"`.

- [ ] **Step 1.3: Migration body**

```python
"""variant barcode unique partial index

Revision ID: 0110_variant_barcode_index
Revises: 0109_add_card_auth
"""
from alembic import op

revision = "0110_variant_barcode_index"
down_revision = "0109_add_card_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop any plain (non-unique) barcode index first if present, so we can
    # replace with the unique partial.
    op.execute("DROP INDEX IF EXISTS ix_product_variants_barcode")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
            ix_product_variants_barcode_unique
        ON product_variants (barcode)
        WHERE barcode IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_product_variants_barcode_unique")
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_variants_barcode ON product_variants (barcode)")
```

- [ ] **Step 1.4: Up/down/up + full suite**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head && pytest 2>&1 | tail -5`
Expected: clean.

- [ ] **Step 1.5: Commit**

```bash
git add backend/alembic/versions/0110_variant_barcode_index.py
git commit -m "feat(db): unique partial index on product_variants.barcode"
```

---

## Task 2: `GET /api/variants/lookup?barcode=X`

Fast single-row lookup so the POS no longer needs to fetch all variants.

**Files:**
- Create: `backend/app/api/variants.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_variants_api.py`

- [ ] **Step 2.1: Failing test**

Create `backend/tests/test_variants_api.py`:

```python
from decimal import Decimal

import pytest

from app.models import Product, ProductVariant


async def _seed(db):
    p = Product(title="Milk", handle="milk"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="1L", sku="SKU-M1",
        barcode="4000400001234", price=Decimal("1.29"),
        pricing_type="fixed", vat_rate=Decimal("7"),
    )
    db.add(v)
    await db.commit(); await db.refresh(v)
    return v


@pytest.mark.asyncio
async def test_lookup_by_barcode_hit(cashier_client, db):
    v = await _seed(db)
    r = await cashier_client.get("/api/variants/lookup?barcode=4000400001234")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == v.id
    assert body["barcode"] == "4000400001234"
    assert body["price"] == "1.29"


@pytest.mark.asyncio
async def test_lookup_by_barcode_miss(cashier_client, db):
    r = await cashier_client.get("/api/variants/lookup?barcode=9999999999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_lookup_requires_staff(client, db):
    await _seed(db)
    r = await client.get("/api/variants/lookup?barcode=4000400001234")
    assert r.status_code == 401
```

- [ ] **Step 2.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_variants_api.py -v`

- [ ] **Step 2.3: Implement router**

Create `backend/app/api/variants.py`:

```python
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff, require_manager_or_above
from app.models import ProductVariant


router = APIRouter(prefix="/api/variants", tags=["variants"])


class VariantOut(BaseModel):
    id: int
    product_id: int
    title: str
    sku: str | None
    barcode: str | None
    price: Decimal
    pricing_type: str
    vat_rate: Decimal
    min_weight_kg: Decimal | None
    max_weight_kg: Decimal | None
    tare_kg: Decimal | None


class VariantUpdate(BaseModel):
    title: str | None = None
    sku: str | None = None
    barcode: str | None = None
    price: Decimal | None = None
    vat_rate: Decimal | None = None
    pricing_type: str | None = None
    min_weight_kg: Decimal | None = None
    max_weight_kg: Decimal | None = None
    tare_kg: Decimal | None = None


def _out(v: ProductVariant) -> VariantOut:
    return VariantOut(
        id=v.id, product_id=v.product_id, title=v.title,
        sku=v.sku, barcode=v.barcode, price=v.price,
        pricing_type=v.pricing_type, vat_rate=v.vat_rate,
        min_weight_kg=v.min_weight_kg, max_weight_kg=v.max_weight_kg, tare_kg=v.tare_kg,
    )


@router.get("/lookup", response_model=VariantOut, dependencies=[Depends(require_any_staff)])
async def lookup(barcode: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    v = (await db.execute(
        select(ProductVariant).where(ProductVariant.barcode == barcode)
    )).scalar_one_or_none()
    if not v:
        raise HTTPException(404, "no variant with that barcode")
    return _out(v)


@router.put("/{variant_id}", response_model=VariantOut, dependencies=[Depends(require_manager_or_above)])
async def update_variant(
    variant_id: int, body: VariantUpdate, db: AsyncSession = Depends(get_db),
):
    v = await db.get(ProductVariant, variant_id)
    if not v:
        raise HTTPException(404, "variant not found")
    data = body.model_dump(exclude_unset=True)
    for k, value in data.items():
        setattr(v, k, value)
    try:
        await db.commit()
    except Exception as e:
        # Catches unique-barcode violations
        raise HTTPException(400, f"update failed: {e}") from e
    await db.refresh(v)
    return _out(v)
```

Register in `backend/app/main.py`:

```python
from app.api.variants import router as variants_router
app.include_router(variants_router)
```

- [ ] **Step 2.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_variants_api.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/api/variants.py backend/app/main.py backend/tests/test_variants_api.py
git commit -m "feat(api): /api/variants/lookup + PUT /api/variants/{id}"
```

---

## Task 3: `PUT /api/variants/{id}` — tests for update paths

Task 2 shipped the PUT endpoint but no tests for it specifically. Add them now (TDD-retrofit pattern: endpoint exists for lookup's sake, we add the update test next).

**Files:**
- Modify: `backend/tests/test_variants_api.py`

- [ ] **Step 3.1: Add update tests**

Append to `backend/tests/test_variants_api.py`:

```python
@pytest.mark.asyncio
async def test_update_variant_price_and_barcode(authed_client, db):
    v = await _seed(db)
    r = await authed_client.put(f"/api/variants/{v.id}", json={
        "price": "1.49", "barcode": "4000400005678",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["price"] == "1.49"
    assert body["barcode"] == "4000400005678"


@pytest.mark.asyncio
async def test_update_variant_duplicate_barcode_400(authed_client, db):
    p = Product(title="X", handle="x"); db.add(p); await db.flush()
    a = ProductVariant(product_id=p.id, title="A", barcode="4000400009999",
                        price=Decimal("1"), pricing_type="fixed", vat_rate=Decimal("7"))
    b = ProductVariant(product_id=p.id, title="B", barcode="4000400008888",
                        price=Decimal("1"), pricing_type="fixed", vat_rate=Decimal("7"))
    db.add_all([a, b]); await db.commit()

    r = await authed_client.put(f"/api/variants/{b.id}", json={
        "barcode": "4000400009999",  # already used by `a`
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_forbidden_for_cashier(cashier_client, db):
    v = await _seed(db)
    r = await cashier_client.put(f"/api/variants/{v.id}", json={"price": "2.00"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_update_clears_barcode_with_null(authed_client, db):
    v = await _seed(db)
    r = await authed_client.put(f"/api/variants/{v.id}", json={"barcode": None})
    assert r.status_code == 200
    assert r.json()["barcode"] is None
```

- [ ] **Step 3.2: Run, confirm pass**

Run: `cd backend && pytest tests/test_variants_api.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 3.3: Commit**

```bash
git add backend/tests/test_variants_api.py
git commit -m "test(variants): coverage for update happy / duplicate / forbidden / null-clear"
```

---

## Task 4: `GET /api/pos-transactions` — recent sales

Admin needs a list to pick a transaction to Storno. Simple paginated list, most recent first, filterable by date range.

**Files:**
- Modify: `backend/app/api/storno.py` (or create `backend/app/api/pos_transactions.py` — cleaner to have its own file)
- Test: `backend/tests/test_pos_transactions_api.py`

- [ ] **Step 4.1: Failing test**

Create `backend/tests/test_pos_transactions_api.py`:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models import PosTransaction, User
from app.services.password import hash_pin


async def _seed(db, *, n: int = 3):
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
             full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)
    now = datetime.now(tz=timezone.utc)
    for i in range(n):
        tid = uuid.uuid4()
        db.add(PosTransaction(
            id=tid, client_id=tid, cashier_user_id=c.id,
            started_at=now, finished_at=now,
            total_gross=Decimal(f"{i+1}.00"), total_net=Decimal(f"{i+1}.00"),
            vat_breakdown={}, payment_breakdown={"cash": f"{i+1}.00"},
            receipt_number=1000 + i,
        ))
    await db.commit()


@pytest.mark.asyncio
async def test_list_pos_transactions_most_recent_first(authed_client, db):
    await _seed(db, n=3)
    r = await authed_client.get("/api/pos-transactions?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3
    # Sorted by receipt_number DESC (most recent)
    nums = [i["receipt_number"] for i in body["items"]]
    assert nums == sorted(nums, reverse=True)


@pytest.mark.asyncio
async def test_list_pos_transactions_requires_staff(client, db):
    await _seed(db, n=1)
    r = await client.get("/api/pos-transactions")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_pos_transactions_pagination(authed_client, db):
    await _seed(db, n=5)
    r = await authed_client.get("/api/pos-transactions?limit=2")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2
```

- [ ] **Step 4.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_pos_transactions_api.py -v`

- [ ] **Step 4.3: Implement endpoint**

Create `backend/app/api/pos_transactions.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff
from app.models import PosTransaction


router = APIRouter(prefix="/api/pos-transactions", tags=["pos-transactions"])


@router.get("", dependencies=[Depends(require_any_staff)])
async def list_pos_transactions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(PosTransaction)
        .order_by(desc(PosTransaction.receipt_number))
        .limit(limit).offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "receipt_number": r.receipt_number,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "total_gross": str(r.total_gross),
                "payment_breakdown": r.payment_breakdown,
                "tse_pending": r.tse_pending,
                "voids_transaction_id": (
                    str(r.voids_transaction_id) if r.voids_transaction_id else None
                ),
            }
            for r in rows
        ],
        "limit": limit, "offset": offset,
    }
```

Register in `main.py`:

```python
from app.api.pos_transactions import router as pos_transactions_router
app.include_router(pos_transactions_router)
```

**Note:** `storno.py` also mounts at `/api/pos-transactions` for the `POST /{id}/void` endpoint. Both routers can share the prefix — FastAPI merges routes by (method, path) so there's no conflict.

- [ ] **Step 4.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_pos_transactions_api.py -v`

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/api/pos_transactions.py backend/app/main.py backend/tests/test_pos_transactions_api.py
git commit -m "feat(api): GET /api/pos-transactions (paginated recent sales)"
```

---

## Task 5: Frontend shared — `variants` + `posTransactions`

**Files:**
- Modify: `frontend/packages/shared/src/api.ts`
- Modify: `frontend/packages/shared/src/types.ts`

- [ ] **Step 5.1: Types**

Append to `frontend/packages/shared/src/types.ts`:

```typescript
export interface VariantDetail {
  id: number;
  product_id: number;
  title: string;
  sku: string | null;
  barcode: string | null;
  price: string;
  pricing_type: "fixed" | "by_weight" | "by_volume";
  vat_rate: string;
  min_weight_kg: string | null;
  max_weight_kg: string | null;
  tare_kg: string | null;
}

export interface PosTransactionListItem {
  id: string;
  receipt_number: number;
  started_at: string;
  finished_at: string | null;
  total_gross: string;
  payment_breakdown: Record<string, string>;
  tse_pending: boolean;
  voids_transaction_id: string | null;
}
```

- [ ] **Step 5.2: API methods**

In `frontend/packages/shared/src/api.ts`, inside the `api` object:

```typescript
  variants: {
    lookup: (barcode: string) =>
      request<VariantDetail>(`/variants/lookup?barcode=${encodeURIComponent(barcode)}`),
    update: (id: number, data: Partial<Omit<VariantDetail, "id" | "product_id">>) =>
      request<VariantDetail>(`/variants/${id}`, {
        method: "PUT", body: JSON.stringify(data),
      }),
  },
  posTransactions: {
    list: (opts?: { limit?: number; offset?: number }) => {
      const p = new URLSearchParams();
      if (opts?.limit != null) p.set("limit", String(opts.limit));
      if (opts?.offset != null) p.set("offset", String(opts.offset));
      const qs = p.toString();
      return request<{ items: PosTransactionListItem[]; limit: number; offset: number }>(
        `/pos-transactions${qs ? "?" + qs : ""}`,
      );
    },
  },
```

Update the type imports at the top of `api.ts` to include `VariantDetail`, `PosTransactionListItem`.

- [ ] **Step 5.3: Build + commit**

```bash
cd frontend && pnpm -r build
git add frontend/packages/shared/src/api.ts frontend/packages/shared/src/types.ts
git commit -m "feat(shared): variants + posTransactions API clients"
```

---

## Task 6: Frontend POS — switch barcode scan to indexed lookup

Today the SalePage's barcode scanner fetches the entire product list and searches client-side (feedback review 03, N+1). Replace with `api.variants.lookup`.

**Files:**
- Modify: `frontend/packages/pos/src/pages/SalePage.tsx`

- [ ] **Step 6.1: Read current scan handler**

Open `frontend/packages/pos/src/pages/SalePage.tsx`. Find the barcode submit handler — it currently calls something like `api.products.list()` and filters in JS. Name the function in your editor (likely `handleBarcodeSubmit` or similar).

- [ ] **Step 6.2: Replace with lookup call**

Change the handler body so that when a scanned barcode is submitted:

```tsx
async function handleBarcodeSubmit(code: string) {
  if (!code) return;
  try {
    const variant = await api.variants.lookup(code);
    addVariantToCart(variant);  // existing helper — passes through existing by-weight prompt
    setBarcodeInput("");
  } catch (e) {
    if ((e as Error).message.includes("404")) {
      toast.error(`No product with barcode ${code}`);
    } else {
      toast.error((e as Error).message);
    }
  }
}
```

If the existing `addVariantToCart` helper expects a different shape than `VariantDetail`, add an adapter inline — most fields will line up (id, price, pricing_type, min/max_weight_kg, vat_rate).

- [ ] **Step 6.3: Remove the now-unused full-list prefetch**

If SalePage did a `useEffect(() => { loadAllProducts() }, [])` on mount solely to support client-side barcode search, delete it. Keep any list used by the "search by name" path — only the barcode path is being reworked.

- [ ] **Step 6.4: Build check**

Run: `cd frontend && pnpm -r build`

- [ ] **Step 6.5: Smoke test (dev server)**

Start the stack (`docker compose up -d`), open the POS, scan or type a known barcode and confirm the item is added without any full product list fetch (verify via browser DevTools Network tab: only a single `GET /api/variants/lookup` should fire per scan).

- [ ] **Step 6.6: Commit**

```bash
git add frontend/packages/pos/src/pages/SalePage.tsx
git commit -m "fix(pos-ui): barcode scan uses indexed lookup, not full product list"
```

---

## Task 7: Frontend admin — variant edit modal

**Files:**
- Create: `frontend/packages/admin/src/pages/VariantEdit.tsx`
- Modify: `frontend/packages/admin/src/pages/Products.tsx`

- [ ] **Step 7.1: Create the modal**

Create `frontend/packages/admin/src/pages/VariantEdit.tsx`:

```tsx
import { useState } from "react";
import { api, type VariantDetail } from "@openmarket/shared";

export function VariantEditModal({
  initial, onSaved, onCancel,
}: {
  initial: VariantDetail;
  onSaved: (v: VariantDetail) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial.title);
  const [sku, setSku] = useState(initial.sku ?? "");
  const [barcode, setBarcode] = useState(initial.barcode ?? "");
  const [price, setPrice] = useState(initial.price);
  const [vatRate, setVatRate] = useState(initial.vat_rate);
  const [pricingType, setPricingType] = useState(initial.pricing_type);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const updated = await api.variants.update(initial.id, {
        title,
        sku: sku || null,
        barcode: barcode || null,
        price,
        vat_rate: vatRate,
        pricing_type: pricingType,
      });
      onSaved(updated);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <form onSubmit={submit} style={{ background: "white", padding: 24, minWidth: 400 }}>
        <h2>Edit variant</h2>
        <div><label>Title: <input value={title} onChange={(e) => setTitle(e.target.value)} required /></label></div>
        <div><label>SKU: <input value={sku} onChange={(e) => setSku(e.target.value)} /></label></div>
        <div><label>Barcode: <input value={barcode} onChange={(e) => setBarcode(e.target.value)} /></label></div>
        <div><label>Price (gross, EUR): <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} required /></label></div>
        <div>
          <label>VAT %:
            <select value={vatRate} onChange={(e) => setVatRate(e.target.value)}>
              <option value="7.00">7%</option>
              <option value="19.00">19%</option>
              <option value="0.00">0%</option>
              <option value="10.70">10.7%</option>
              <option value="5.50">5.5%</option>
            </select>
          </label>
        </div>
        <div>
          <label>Pricing:
            <select value={pricingType} onChange={(e) => setPricingType(e.target.value as "fixed" | "by_weight")}>
              <option value="fixed">Fixed</option>
              <option value="by_weight">By weight</option>
            </select>
          </label>
        </div>
        {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
        <div style={{ marginTop: 12 }}>
          <button type="submit" disabled={busy}>{busy ? "Saving..." : "Save"}</button>
          <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 7.2: Wire an "Edit" button on each variant row in `Products.tsx`**

Find the existing variant row renderer in `frontend/packages/admin/src/pages/Products.tsx`. Add an Edit button and a state slot for the modal:

```tsx
import { VariantEditModal } from "./VariantEdit";
import type { VariantDetail } from "@openmarket/shared";

// inside the Products component body
const [editing, setEditing] = useState<VariantDetail | null>(null);

// inside each variant row's JSX, add:
<button onClick={() => setEditing(variant)}>Edit</button>

// near the end of the component render:
{editing && (
  <VariantEditModal
    initial={editing}
    onSaved={(v) => { setEditing(null); void reloadProducts(); }}
    onCancel={() => setEditing(null)}
  />
)}
```

`reloadProducts` is the existing load function; rename as needed to match.

- [ ] **Step 7.3: Build + smoke**

Run: `cd frontend && pnpm -r build`

Start the dev server and verify: open Products, click Edit on any variant, change the price and VAT rate, save, confirm list reflects the change, and confirm POS scan of the variant's barcode uses the new price.

- [ ] **Step 7.4: Commit**

```bash
git add frontend/packages/admin/src/pages/VariantEdit.tsx frontend/packages/admin/src/pages/Products.tsx
git commit -m "feat(admin-ui): inline variant edit modal (price/barcode/sku/vat)"
```

---

## Task 8: Frontend admin — Recent Sales + Storno

**Files:**
- Create: `frontend/packages/admin/src/pages/RecentSales.tsx`
- Modify: `frontend/packages/admin/src/App.tsx`

- [ ] **Step 8.1: Create the page**

Create `frontend/packages/admin/src/pages/RecentSales.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api, type PosTransactionListItem } from "@openmarket/shared";

export function RecentSales() {
  const [items, setItems] = useState<PosTransactionListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function reload() {
    try { setItems((await api.posTransactions.list({ limit: 100 })).items); }
    catch (e) { setError((e as Error).message); }
  }

  useEffect(() => { void reload(); }, []);

  async function handleVoid(id: string) {
    if (!confirm(`Void transaction ${id}?`)) return;
    setBusy(id);
    try {
      await api.storno.void(id);
      await reload();
    } catch (e) {
      alert(`Void failed: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div style={{ maxWidth: 1000, margin: "32px auto" }}>
      <h1>Recent sales</h1>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      <table style={{ width: "100%" }}>
        <thead>
          <tr>
            <th>Receipt</th><th>Started</th><th>Total</th><th>Payment</th><th>Void?</th><th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.id} style={{ opacity: it.voids_transaction_id ? 0.5 : 1 }}>
              <td>{it.receipt_number}</td>
              <td>{new Date(it.started_at).toLocaleString()}</td>
              <td>EUR {it.total_gross}</td>
              <td>{Object.entries(it.payment_breakdown).map(([k, v]) => `${k} ${v}`).join(", ") || "-"}</td>
              <td>{it.voids_transaction_id ? "voided/void-row" : "-"}</td>
              <td>
                {!it.voids_transaction_id && (
                  <button onClick={() => handleVoid(it.id)} disabled={busy === it.id}>
                    {busy === it.id ? "..." : "Storno"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 8.2: Route + nav**

In `frontend/packages/admin/src/App.tsx`:

```tsx
import { RecentSales } from "./pages/RecentSales";
// ...
<Route path="/sales" element={<RecentSales />} />
```

Add a nav link "Sales" for `owner` and `manager`.

- [ ] **Step 8.3: Build + smoke + commit**

Run: `cd frontend && pnpm -r build`

```bash
git add frontend/packages/admin/src/pages/RecentSales.tsx frontend/packages/admin/src/App.tsx
git commit -m "feat(admin-ui): Recent Sales list with Storno button"
```

---

## Self-Review Checklist

1. **Feedback 03 (shop manager) dealbreaker: no product edit UI** — Tasks 2 (update endpoint), 3 (update tests), 7 (edit modal). ✓
2. **Feedback 03 dealbreaker: barcode lookup N+1** — Tasks 1 (unique partial index), 2 (`/api/variants/lookup`), 6 (POS rewire). ✓
3. **Feedback 03 dealbreaker: no void/refund** — Covered by Plan D's Storno plus Task 4 (recent-sales list) + Task 8 (admin Storno button). The POS has its own "Storno last sale" button from Plan D Task 14; admin now has the broader "Storno any recent sale" flow. ✓
4. **Duplicate-barcode prevention** — Task 1's unique partial index + Task 3's test_update_variant_duplicate_barcode_400. ✓
5. **Cashier cannot edit prices** — Task 3's test_update_forbidden_for_cashier asserts 403; dependency is `require_manager_or_above`. ✓

**Placeholder scan:** none.

**Type consistency:**
- `VariantDetail` TS type mirrors `VariantOut` Python schema — all fields present, Decimals as strings on the wire. ✓
- `PosTransactionListItem` TS type mirrors backend response shape exactly (ids as strings, decimals as strings). ✓
- `api.storno.void(id: string)` in Task 8 matches the signature introduced in Plan D Task 9. ✓

**Tracked Phase 2:**

- Bulk CSV import for variants.
- Inline table editing (the modal is fine for day-1 but a grid editor is friendlier).
- Return-reason taxonomy (today, Storno is binary void; returns with reasons are separate from fiscal Storno and already partly handled by `returns` router).
- Recent Sales: filter by date, cashier, payment method.

---

**Plan complete.** All five plans (A–E) now live in `docs/superpowers/plans/`.
