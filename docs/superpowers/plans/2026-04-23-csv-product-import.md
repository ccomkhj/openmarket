# CSV Product Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner seed the catalog by uploading a CSV, so they never have to add 500 products one-by-one through the UI on day one.

**Architecture:** One new backend endpoint `POST /api/products/import-csv` (multipart file upload, manager+). Parses CSV rows into `ProductCreate` + one `VariantCreate` each, inserts via the existing service path. Returns a summary (`created`, `skipped`, `errors[]`). Admin UI adds an "Import CSV" button next to the product search that posts the file and shows the summary as a toast.

**Tech Stack:** FastAPI + python's `csv` stdlib (no new deps), existing SQLAlchemy models, React admin page.

---

### Task 1: Backend endpoint

**Files:**
- Modify: `backend/app/api/products.py`

- [ ] **Step 1: Add the import endpoint**

Append to `backend/app/api/products.py` (after the existing `create_product` or at end of file — location doesn't matter):

```python
import csv
import io


@router.post("/products/import-csv")
async def import_products_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """CSV columns (header row required):
    title, handle, barcode, sku, price, status(optional, default=active)
    One variant per row. Duplicate handles are skipped.
    """
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    required = {"title", "handle", "barcode", "sku", "price"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise HTTPException(400, f"missing CSV columns: {sorted(missing)}")

    existing_handles = set(
        (await db.execute(select(Product.handle))).scalars().all()
    )
    created = 0
    skipped = 0
    errors: list[str] = []

    from decimal import Decimal, InvalidOperation
    for i, row in enumerate(reader, start=2):
        handle = (row.get("handle") or "").strip()
        title = (row.get("title") or "").strip()
        if not handle or not title:
            errors.append(f"row {i}: missing handle or title")
            continue
        if handle in existing_handles:
            skipped += 1
            continue
        try:
            price = Decimal((row.get("price") or "0").strip())
        except (InvalidOperation, ValueError):
            errors.append(f"row {i}: bad price '{row.get('price')}'")
            continue
        product = Product(
            title=title,
            handle=handle,
            description="",
            product_type="",
            status=(row.get("status") or "active").strip(),
            tags=[],
        )
        variant = ProductVariant(
            title="Default",
            sku=(row.get("sku") or "").strip(),
            barcode=(row.get("barcode") or "").strip(),
            price=price,
            position=0,
            pricing_type="fixed",
        )
        variant.inventory_item = InventoryItem()
        product.variants.append(variant)
        db.add(product)
        existing_handles.add(handle)
        created += 1

    await db.commit()
    return {"created": created, "skipped": skipped, "errors": errors}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/products.py
git commit -m "feat(api): CSV product import endpoint"
```

---

### Task 2: Shared API client

**Files:**
- Modify: `frontend/packages/shared/src/api.ts` (products block)

- [ ] **Step 1: Add `importCsv` under `products`**

Find the `products: { ... }` block in `api.ts` and add a method:

```typescript
    importCsv: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/products/import-csv", { method: "POST", credentials: "include", body: fd });
      if (!res.ok) throw new Error(await res.text());
      return (await res.json()) as { created: number; skipped: number; errors: string[] };
    },
```

- [ ] **Step 2: Commit**

```bash
git add frontend/packages/shared/src/api.ts
git commit -m "feat(shared): products.importCsv client"
```

---

### Task 3: Admin UI — Import CSV button

**Files:**
- Modify: `frontend/packages/admin/src/pages/ProductsInventoryPage.tsx`

- [ ] **Step 1: Add upload button + handler**

Near the top of the `ProductsInventoryPage` component (after existing state declarations), add:

```tsx
  const fileInputRef = useRef<HTMLInputElement>(null);
  const onPickCsv = () => fileInputRef.current?.click();
  const onCsvChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    try {
      const r = await api.products.importCsv(f);
      toast(`Imported ${r.created} product(s), skipped ${r.skipped}${r.errors.length ? `, ${r.errors.length} errors` : ""}`);
      if (r.errors.length) console.warn("CSV import errors", r.errors);
      // Reload list
      setLoading(true);
      const ps = await api.products.list({});
      setProducts(ps);
      setLoading(false);
    } catch (err: any) {
      toast(`Import failed: ${err.message}`, "error");
    }
  };
```

Then render a button + hidden file input near the search bar. Put this right after the search `<input />` in the page header area:

```tsx
          <input ref={fileInputRef} type="file" accept=".csv,text/csv" onChange={onCsvChange} style={{ display: "none" }} />
          <Button variant="secondary" size="sm" onClick={onPickCsv}>Import CSV</Button>
```

Also add `useRef` to the `react` import at the top of the file if it isn't already there.

- [ ] **Step 2: Build**

Run: `cd frontend && pnpm -F @openmarket/admin build`
Expected: no TS errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/admin/src/pages/ProductsInventoryPage.tsx
git commit -m "feat(admin): import products from CSV"
```

---

### Task 4: Add an example CSV + docs

**Files:**
- Create: `docs/ops/product-import.md`
- Create: `docs/ops/example-products.csv`

- [ ] **Step 1: Write docs**

`docs/ops/product-import.md`:

```markdown
# CSV Product Import

Upload a CSV from the Admin → Products page (Import CSV button) to bulk-create products. One row = one product with one default variant.

## Columns (header row required)

| column    | required | notes                              |
|-----------|----------|------------------------------------|
| title     | yes      | product title                      |
| handle    | yes      | URL slug; must be unique           |
| barcode   | yes      | EAN/UPC for POS scanning (may be empty string) |
| sku       | yes      | internal SKU (may be empty string) |
| price     | yes      | decimal, e.g. `4.99`               |
| status    | no       | `active` (default) or `draft`      |

Rows with duplicate handles are skipped. Rows with bad prices or missing title/handle are reported in the result summary.

See `example-products.csv` for a starter file.
```

`docs/ops/example-products.csv`:

```csv
title,handle,barcode,sku,price,status
Organic Bananas 1kg,organic-bananas-1kg,4011200296906,BAN-ORG-1KG,2.49,active
Whole Milk 1L,whole-milk-1l,4008400401621,MLK-WHL-1L,1.29,active
Sourdough Bread 500g,sourdough-500g,4260123456781,BRD-SRD-500,3.80,active
```

- [ ] **Step 2: Commit**

```bash
git add docs/ops/product-import.md docs/ops/example-products.csv
git commit -m "docs: CSV product import guide"
```

---

## Self-review

- Spec coverage: endpoint (T1), client (T2), UI (T3), docs+example (T4).
- No placeholders: all code blocks inline.
- Type consistency: `importCsv` returns `{ created, skipped, errors }`, handler destructures the same shape.
