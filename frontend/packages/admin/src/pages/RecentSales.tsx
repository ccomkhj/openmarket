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
