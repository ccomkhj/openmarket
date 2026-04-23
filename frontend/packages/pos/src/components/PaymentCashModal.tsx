import { useState, useMemo } from "react";
import { api, type CashPaymentResult } from "@openmarket/shared";

function quickTenders(total: number): number[] {
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
