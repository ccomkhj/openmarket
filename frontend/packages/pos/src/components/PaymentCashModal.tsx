import { useState } from "react";
import { api, type CashPaymentResult } from "@openmarket/shared";

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
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <form onSubmit={submit} style={{ background: "white", padding: 24, minWidth: 320 }}>
        <h2>Cash payment</h2>
        <p>Total due: <strong>EUR {total}</strong></p>
        <label>
          Tendered:
          <input
            inputMode="decimal" pattern="[0-9.]*" autoFocus
            value={tendered} onChange={(e) => setTendered(e.target.value)}
            style={{ marginLeft: 8, fontSize: 18, width: 100 }}
          />
        </label>
        <p>Change: EUR {(Math.max(0, parseFloat(tendered || "0") - parseFloat(total))).toFixed(2)}</p>
        {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={busy || parseFloat(tendered || "0") < parseFloat(total)}>
          {busy ? "Signing..." : "Confirm"}
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
      </form>
    </div>
  );
}
