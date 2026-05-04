import { useEffect, useState } from "react";
import { api, Button, ConfirmDialog, ModalShell, Spinner, baseStyles, colors, radius, spacing, useEscapeKey } from "@openmarket/shared";
import type { ParkedSale } from "@openmarket/shared";

interface Props {
  onRecall: (sale: ParkedSale) => void;
  onClose: () => void;
}

function ageLabel(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.round(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.round(hr / 24)}d ago`;
}

export function ParkedSalesPicker({ onRecall, onClose }: Props) {
  const [sales, setSales] = useState<ParkedSale[] | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [confirmCancel, setConfirmCancel] = useState<ParkedSale | null>(null);

  const reload = () => {
    setError("");
    api.parkedSales.list()
      .then(setSales)
      .catch(() => setError("Could not load parked sales."));
  };

  useEffect(() => { reload(); }, []);

  // Escape closes the inner confirm first if open, otherwise the picker itself.
  // Disable ModalShell's own escape so the picker handles both layers itself.
  useEscapeKey(() => { if (confirmCancel) setConfirmCancel(null); else onClose(); });

  const cancel = async (id: number) => {
    setBusyId(id);
    try {
      await api.parkedSales.cancel(id);
      reload();
    } catch {
      setError("Cancel failed.");
    } finally { setBusyId(null); setConfirmCancel(null); }
  };

  return (
    <ModalShell onClose={onClose} width="lg" align="top" closeOnEscape={false}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
        <h3 style={{ margin: 0 }}>Parked sales</h3>
        <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
      </div>

      {sales === null && <Spinner label="Loading..." />}

      {sales && sales.length === 0 && (
        <div style={{ padding: spacing.lg, color: colors.textSecondary, textAlign: "center" }}>
          <p style={{ margin: 0, fontSize: 14 }}>No parked sales right now.</p>
          <p style={{ margin: "6px 0 0", fontSize: 12 }}>
            Use <strong>Park</strong> in the cart header to set one aside.
          </p>
        </div>
      )}

      {confirmCancel && (
        <ConfirmDialog
          title="Cancel parked sale"
          message={`Discard ${confirmCancel.item_count} item${confirmCancel.item_count === 1 ? "" : "s"} for ${confirmCancel.customer_name ?? "walk-in"}?`}
          confirmLabel="Discard"
          variant="danger"
          loading={busyId === confirmCancel.id}
          onConfirm={() => cancel(confirmCancel.id)}
          onCancel={() => setConfirmCancel(null)}
        />
      )}

      {sales && sales.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: spacing.sm, maxHeight: "55vh", overflowY: "auto" }}>
          {sales.map((s) => (
            <div key={s.id} style={{
              ...baseStyles.card,
              padding: spacing.md,
              display: "flex", alignItems: "center", gap: spacing.md,
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>
                  {s.customer_name ?? "Walk-in"}
                  <span style={{ color: colors.textSecondary, fontWeight: 400, fontSize: 13, marginLeft: 8 }}>
                    · {s.item_count} item{s.item_count === 1 ? "" : "s"} · {ageLabel(s.created_at)}
                  </span>
                </div>
                {s.note && (
                  <div style={{ color: colors.textSecondary, fontSize: 13, marginTop: 2 }}>
                    {s.note}
                  </div>
                )}
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => onRecall(s)}
              >Recall</Button>
              <Button
                variant="danger"
                size="sm"
                loading={busyId === s.id}
                onClick={() => setConfirmCancel(s)}
              >Cancel</Button>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div style={{
          marginTop: spacing.md,
          background: colors.dangerSurface, color: colors.danger,
          padding: "8px 12px", borderRadius: radius.sm, fontSize: 13,
        }}>{error}</div>
      )}
    </ModalShell>
  );
}
