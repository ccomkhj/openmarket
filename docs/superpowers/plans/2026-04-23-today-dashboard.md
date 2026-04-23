# Today Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Turn the existing Analytics page into a usable "today at a glance" landing: add a `Today` period button (1 day) and a low-stock count card so the owner opens admin and immediately sees shop health.

**Architecture:** One new small endpoint `GET /api/inventory-levels/low-stock-count` that counts rows where `available <= low_stock_threshold` across a location. Frontend adds a `Today` button to AnalyticsPage and a `Low stock` metric card that hits the new endpoint.

**Tech Stack:** FastAPI, React.

---

### Task 1: Low-stock count endpoint

**Files:**
- Modify: `backend/app/api/inventory.py`

- [ ] **Step 1: Add endpoint**

Append to `backend/app/api/inventory.py`:

```python
@router.get("/inventory-levels/low-stock-count")
async def low_stock_count(location_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InventoryLevel).where(
            InventoryLevel.location_id == location_id,
            InventoryLevel.available <= InventoryLevel.low_stock_threshold,
        )
    )
    return {"count": len(result.scalars().all())}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/inventory.py
git commit -m "feat(api): low-stock count endpoint"
```

---

### Task 2: Shared API client

**Files:**
- Modify: `frontend/packages/shared/src/api.ts` (inventory block)

- [ ] **Step 1: Add `lowStockCount`**

In the `inventory: { ... }` block add:

```typescript
    lowStockCount: (locationId: number) =>
      request<{ count: number }>(`/inventory-levels/low-stock-count?location_id=${locationId}`),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/packages/shared/src/api.ts
git commit -m "feat(shared): inventory.lowStockCount client"
```

---

### Task 3: AnalyticsPage — Today button + low-stock card

**Files:**
- Modify: `frontend/packages/admin/src/pages/AnalyticsPage.tsx`

- [ ] **Step 1: Add state + fetch**

Replace `const [days, setDays] = useState(30);` with:

```tsx
  const [days, setDays] = useState(1);
  const [lowStock, setLowStock] = useState<number | null>(null);
```

Add below `useEffect(() => { loadSummary(days); }, [days]);`:

```tsx
  useEffect(() => {
    api.inventory.lowStockCount(1)
      .then((r) => setLowStock(r.count))
      .catch(() => setLowStock(null));
  }, []);
```

- [ ] **Step 2: Add Today button and rename header**

In the header `<h2>Analytics</h2>`, change to `<h2>Today</h2>`.

Add a Today button in the period buttons row, right before `7d`:

```tsx
          <button onClick={() => setDays(1)} style={periodStyle(1)}>Today</button>
```

- [ ] **Step 3: Render low-stock card**

Find the metrics row (where `metricCard(...)` is called for revenue/orders/AOV) and add one more card. Example (near the other `metricCard` calls):

```tsx
          {lowStock !== null && metricCard("Low-stock items", String(lowStock), lowStock > 0 ? colors.danger : undefined)}
```

- [ ] **Step 4: Build**

Run: `cd frontend && pnpm -F @openmarket/admin build`

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/admin/src/pages/AnalyticsPage.tsx
git commit -m "feat(admin): today dashboard with low-stock card"
```

---

## Self-review

- Spec coverage: endpoint (T1), client (T2), UI (T3).
- No placeholders.
- Type consistency: `lowStockCount` returns `{ count: number }`.
