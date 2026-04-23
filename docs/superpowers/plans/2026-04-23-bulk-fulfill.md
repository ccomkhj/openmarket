# Bulk Fulfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Give the manager a single "Fulfill all visible" button on the Orders page so 30 web orders is one click, not 90.

**Architecture:** Frontend-only. Iterates the currently-visible `orders[]` list and calls `api.fulfillments.create` for each, with a confirm dialog first. Uses `Promise.all` with best-effort error handling — a fail on one doesn't abort the rest.

**Tech Stack:** React.

---

### Task 1: Add bulk fulfill button

**Files:**
- Modify: `frontend/packages/admin/src/pages/OrdersPage.tsx`

- [ ] **Step 1: Add state, handler, and confirm dialog**

Near existing state:

```tsx
  const [bulkBusy, setBulkBusy] = useState(false);
  const [confirmBulk, setConfirmBulk] = useState(false);
```

Add `ConfirmDialog, useToast` to the existing `@openmarket/shared` import if not present. Check toast availability.

Add handler next to `fulfill`:

```tsx
  const fulfillAllVisible = async () => {
    setConfirmBulk(false);
    setBulkBusy(true);
    const results = await Promise.allSettled(
      orders.map((o) => api.fulfillments.create(o.id, { status: "delivered" })),
    );
    const failed = results.filter((r) => r.status === "rejected").length;
    setBulkBusy(false);
    await loadOrders();
    if (failed === 0) toast(`Fulfilled ${results.length} order(s)`);
    else toast(`Fulfilled ${results.length - failed}, failed ${failed}`, "error");
  };
```

- [ ] **Step 2: Render button + confirm dialog**

In the header row (the `Orders` header), change the right side from just the Export button to:

```tsx
        <div style={{ display: "flex", gap: spacing.sm }}>
          <Button
            variant="primary" size="sm"
            disabled={tab !== "unfulfilled" || orders.length === 0 || bulkBusy}
            onClick={() => setConfirmBulk(true)}>
            {bulkBusy ? "Fulfilling..." : `Fulfill all (${orders.length})`}
          </Button>
          <Button variant="secondary" size="sm" onClick={handleExport} disabled={orders.length === 0}>Export CSV</Button>
        </div>
```

And at the end of the JSX (before the closing `</div>`):

```tsx
      {confirmBulk && (
        <ConfirmDialog
          title="Fulfill all visible orders"
          message={`This will mark ${orders.length} order(s) as delivered. This cannot be undone in bulk.`}
          confirmLabel="Fulfill all"
          variant="primary"
          onConfirm={fulfillAllVisible}
          onCancel={() => setConfirmBulk(false)}
        />
      )}
```

- [ ] **Step 3: Ensure imports**

The top `@openmarket/shared` import must include: `Button, Spinner, ConfirmDialog, useToast, colors, baseStyles, spacing, radius, useDebounce, exportCsv, api`.

Add `const { toast } = useToast();` near the other state hooks if missing.

- [ ] **Step 4: Build**

Run: `cd frontend && pnpm -F @openmarket/admin build`
Expected: no TS errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/admin/src/pages/OrdersPage.tsx
git commit -m "feat(admin): fulfill-all-visible bulk action on Orders page"
```

---

## Self-review

- Spec coverage: button (T1.2), handler (T1.1), confirm (T1.2).
- No placeholders.
- Disabled when tab is "fulfilled" (nothing to do) or list empty.
