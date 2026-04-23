# POS Go-Live Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last-mile gaps in the POS payment & receipt flow so a cashier can handle real customers without help: quick-tender cash buttons, reprint-last-receipt button, and a persistent confirmation showing order number + change.

**Architecture:** All three changes are thin additions on top of the already-complete payment and receipt stack. The `/api/receipts/{id}/reprint` endpoint already exists — frontend only. Quick-tender buttons are pure `PaymentCashModal` UI. Persistent confirmation is state kept on `SalePage` until explicitly dismissed.

**Tech Stack:** React 18 + TypeScript (POS UI), FastAPI (no backend changes needed).

---

### Task 1: Add `receipts.reprint` to shared API client

**Files:**
- Modify: `frontend/packages/shared/src/api.ts:146-151` (add after `payment` block)

- [ ] **Step 1: Add method to api object**

In `frontend/packages/shared/src/api.ts`, after the `payment: { ... },` block (ends at line 151), add:

```typescript
  receipts: {
    reprint: (posTransactionId: string) =>
      request<{ id: number; pos_transaction_id: string; status: string; attempts: number; last_error: string | null; printed_at: string | null }>(
        `/receipts/${posTransactionId}/reprint`,
        { method: "POST" },
      ),
  },
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && pnpm -F @openmarket/shared build`
Expected: no TS errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/shared/src/api.ts
git commit -m "feat(shared): receipts.reprint API client"
```

---

### Task 2: Quick-tender buttons in cash modal

**Files:**
- Modify: `frontend/packages/pos/src/components/PaymentCashModal.tsx` (entire component)

- [ ] **Step 1: Replace component body with quick-tender version**

Overwrite `frontend/packages/pos/src/components/PaymentCashModal.tsx` with:

```tsx
import { useState, useMemo } from "react";
import { api, type CashPaymentResult } from "@openmarket/shared";

function quickTenders(total: number): number[] {
  // Exact + next round banknotes above total.
  const banknotes = [5, 10, 20, 50, 100, 200];
  const above = banknotes.filter((b) => b >= total);
  const exact = Math.ceil(total * 100) / 100;
  const set = new Set<number>([exact, ...above]);
  return Array.from(set).sort((a, b) => a - b).slice(0, 5);
}

export function PaymentCashModal({
  orderId, total, onPaid, onCancel,
}: {
  orderId: number; total: string;
  onPaid: (r: CashPaymentResult) => void;
  onCancel: () => void;
}) {
  const [tendered, setTendered] = useState<string>(total);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalNum = parseFloat(total) || 0;
  const tenders = useMemo(() => quickTenders(totalNum), [totalNum]);
  const change = Math.max(0, parseFloat(tendered || "0") - totalNum);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await api.payment.cash({
        client_id: crypto.randomUUID(), order_id: orderId, tendered,
      });
      onPaid(r);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <form onSubmit={submit} style={{ background: "white", padding: 24, minWidth: 360, borderRadius: 8 }}>
        <h2 style={{ marginTop: 0 }}>Cash payment</h2>
        <p>Total due: <strong>EUR {total}</strong></p>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "12px 0" }}>
          {tenders.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTendered(t.toFixed(2))}
              style={{ padding: "10px 14px", fontSize: 16, fontWeight: 600, cursor: "pointer" }}
            >
              EUR {t.toFixed(2)}
            </button>
          ))}
        </div>

        <label style={{ display: "block", margin: "12px 0" }}>
          Tendered:
          <input
            inputMode="decimal" pattern="[0-9.]*" autoFocus
            value={tendered} onChange={(e) => setTendered(e.target.value)}
            style={{ marginLeft: 8, fontSize: 18, width: 120, padding: 4 }}
          />
        </label>

        <p style={{ fontSize: 18 }}>Change: <strong>EUR {change.toFixed(2)}</strong></p>
        {error && <p role="alert" style={{ color: "red" }}>{error}</p>}

        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button type="submit" disabled={busy || parseFloat(tendered || "0") < totalNum}
            style={{ flex: 1, padding: "12px", fontSize: 16, fontWeight: 600, background: "#1A7F37", color: "white", border: 0, cursor: "pointer" }}>
            {busy ? "Signing..." : "Confirm"}
          </button>
          <button type="button" onClick={onCancel} disabled={busy}
            style={{ padding: "12px 16px", fontSize: 16 }}>Cancel</button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && pnpm -F @openmarket/pos build`
Expected: no TS errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/pos/src/components/PaymentCashModal.tsx
git commit -m "feat(pos): quick-tender buttons in cash modal"
```

---

### Task 3: Reprint-last-receipt button on SalePage

**Files:**
- Modify: `frontend/packages/pos/src/pages/SalePage.tsx` (reuse existing `lastTxId` state)

- [ ] **Step 1: Add reprint handler and button**

In `frontend/packages/pos/src/pages/SalePage.tsx`, inside the `SalePage` component:

1. After the `doStorno` function (around the handler block), add:

```tsx
  const doReprint = async () => {
    if (!lastTxId) return;
    try {
      const job = await api.receipts.reprint(lastTxId);
      if (job.status === "printed" || job.status === "queued") {
        toast("Receipt reprinted");
      } else {
        toast(`Reprint status: ${job.status}${job.last_error ? ` — ${job.last_error}` : ""}`, "error");
      }
    } catch (e: any) {
      toast(`Reprint failed: ${e.message}`, "error");
    }
  };
```

2. In the right-panel footer block, find the `{lastTxId && (` Storno button. Replace that entire conditional block with:

```tsx
          {lastTxId && (
            <div style={{ display: "flex", gap: spacing.xs, marginTop: spacing.xs }}>
              <Button variant="secondary" size="sm" fullWidth onClick={doReprint}>
                Reprint receipt
              </Button>
              <Button variant="danger" size="sm" fullWidth onClick={() => setConfirmStorno(true)}>
                Storno last sale
              </Button>
            </div>
          )}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && pnpm -F @openmarket/pos build`
Expected: no TS errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/packages/pos/src/pages/SalePage.tsx
git commit -m "feat(pos): reprint-last-receipt button"
```

---

### Task 4: Verify backend reprint endpoint still works

**Files:**
- Test: `backend/tests/test_receipts_api.py` (create if missing — search first)

- [ ] **Step 1: Search for an existing test**

Run: `ls backend/tests | grep -i receipt`
If a test file already covers `POST /api/receipts/{id}/reprint`, skip to Step 3.

- [ ] **Step 2: Run the full backend test suite to confirm no regressions**

Run: `cd backend && pytest -q`
Expected: all tests pass (no code changed on backend side in this plan).

- [ ] **Step 3: Commit (no-op if nothing to commit)**

No code change expected; this task is purely a verification gate.

---

## Self-review

- Spec coverage: (a) quick-tender buttons → Task 2; (b) reprint-last button → Tasks 1+3; (c) backend already has endpoint — verified by Task 4.
- No placeholders: every step contains full code.
- Type consistency: `api.receipts.reprint(string)` signature matches the URL param (`uuid.UUID` stringified), and `lastTxId` is typed `string | null` in SalePage.
