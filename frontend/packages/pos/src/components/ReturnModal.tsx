import { useState } from "react";
import { api, Button, Spinner, colors, spacing, radius, baseStyles } from "@openmarket/shared";
import type { Order } from "@openmarket/shared";

interface ReturnModalProps {
  onClose: () => void;
}

interface ReturnQty {
  [lineItemId: number]: number;
}

export function ReturnModal({ onClose }: ReturnModalProps) {
  const [step, setStep] = useState<"lookup" | "select" | "success">("lookup");
  const [orderNumber, setOrderNumber] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [returnQty, setReturnQty] = useState<ReturnQty>({});
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refundAmount, setRefundAmount] = useState(0);

  const lookupOrder = async () => {
    if (!orderNumber.trim()) return;
    setLoading(true);
    setError("");
    try {
      const found = await api.orders.lookup(orderNumber.trim());
      setOrder(found);
      const initial: ReturnQty = {};
      for (const li of found.line_items) {
        initial[li.id] = 0;
      }
      setReturnQty(initial);
      setStep("select");
    } catch (e: any) {
      setError(e.message || "Order not found");
    } finally {
      setLoading(false);
    }
  };

  const updateQty = (lineItemId: number, qty: number) => {
    const li = order!.line_items.find((i) => i.id === lineItemId);
    if (!li) return;
    const clamped = Math.max(0, Math.min(qty, li.quantity));
    setReturnQty((prev) => ({ ...prev, [lineItemId]: clamped }));
  };

  const computeTotal = () => {
    if (!order) return 0;
    return order.line_items.reduce((sum, li) => {
      const qty = returnQty[li.id] ?? 0;
      return sum + parseFloat(li.price) * qty;
    }, 0);
  };

  const processReturn = async () => {
    if (!order) return;
    const items = order.line_items
      .filter((li) => (returnQty[li.id] ?? 0) > 0)
      .map((li) => ({ line_item_id: li.id, quantity: returnQty[li.id] }));

    if (items.length === 0) {
      setError("Select at least one item to return.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/returns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: order.id, reason, items }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(data.detail || `HTTP ${response.status}`);
      }
      const result = await response.json();
      setRefundAmount(parseFloat(result.total_refund));
      setStep("success");
    } catch (e: any) {
      setError(e.message || "Failed to process return");
    } finally {
      setLoading(false);
    }
  };

  const overlayStyle: React.CSSProperties = {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.5)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  };

  const modalStyle: React.CSSProperties = {
    background: colors.surface,
    borderRadius: radius.md,
    padding: spacing.xl,
    width: 480,
    maxWidth: "90vw",
    maxHeight: "85vh",
    overflowY: "auto",
    boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
  };

  return (
    <div style={overlayStyle} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={modalStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
          <h2 style={{ margin: 0, color: colors.textPrimary }}>Process Return</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>&#10005;</Button>
        </div>

        {step === "lookup" && (
          <div>
            <label style={{ display: "block", fontWeight: 600, marginBottom: "6px", fontSize: "13px", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Order Number
            </label>
            <div style={{ display: "flex", gap: spacing.sm }}>
              <input
                value={orderNumber}
                onChange={(e) => setOrderNumber(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") lookupOrder(); }}
                placeholder="e.g. ORD-20240101120000-1001"
                style={{ ...baseStyles.input, flex: 1 }}
                autoFocus
              />
              <Button variant="primary" onClick={lookupOrder} disabled={loading || !orderNumber.trim()}>
                {loading ? <Spinner size={16} /> : "Look Up"}
              </Button>
            </div>
            {error && (
              <div style={{ marginTop: spacing.sm, color: colors.danger, fontSize: "14px" }}>{error}</div>
            )}
          </div>
        )}

        {step === "select" && order && (
          <div>
            <div style={{ marginBottom: spacing.md, padding: "10px 14px", background: colors.surfaceMuted, borderRadius: radius.sm, fontSize: "14px" }}>
              <strong>Order:</strong> {order.order_number}<br />
              <span style={{ color: colors.textSecondary }}>Total: ${parseFloat(order.total_price).toFixed(2)}</span>
            </div>

            <label style={{ display: "block", fontWeight: 600, marginBottom: "8px", fontSize: "13px", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Items to Return
            </label>
            <div style={{ marginBottom: spacing.md }}>
              {order.line_items.map((li) => (
                <div key={li.id} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "10px 12px", marginBottom: "6px",
                  background: colors.surface, borderRadius: radius.sm,
                  border: `1px solid ${colors.border}`,
                }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: "14px" }}>{li.title}</div>
                    <div style={{ color: colors.textSecondary, fontSize: "13px" }}>
                      ${li.price} &times; {li.quantity} ordered
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <Button variant="secondary" size="sm" onClick={() => updateQty(li.id, (returnQty[li.id] ?? 0) - 1)}>-</Button>
                    <input
                      value={returnQty[li.id] ?? 0}
                      onChange={(e) => { const v = parseInt(e.target.value); if (!isNaN(v)) updateQty(li.id, v); }}
                      style={{ width: 40, textAlign: "center", padding: "4px", border: `1px solid ${colors.borderStrong}`, borderRadius: radius.sm, fontSize: "14px", fontWeight: 600 }}
                    />
                    <Button variant="secondary" size="sm" onClick={() => updateQty(li.id, (returnQty[li.id] ?? 0) + 1)}>+</Button>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ marginBottom: spacing.md }}>
              <label style={{ display: "block", fontWeight: 600, marginBottom: "6px", fontSize: "13px", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                Reason (optional)
              </label>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. damaged, wrong item..."
                style={baseStyles.input}
              />
            </div>

            <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: spacing.md, marginBottom: spacing.md, textAlign: "right" }}>
              <span style={{ fontSize: "18px", fontWeight: 700 }}>
                Refund: ${computeTotal().toFixed(2)}
              </span>
            </div>

            {error && (
              <div style={{ marginBottom: spacing.sm, padding: "10px 14px", background: colors.dangerSurface, color: colors.danger, borderRadius: radius.sm, fontSize: "14px" }}>{error}</div>
            )}

            <div style={{ display: "flex", gap: spacing.sm }}>
              <Button variant="secondary" onClick={() => { setStep("lookup"); setError(""); }} style={{ flex: 1 }}>Back</Button>
              <Button variant="primary" onClick={processReturn} disabled={loading || computeTotal() === 0} style={{ flex: 2 }}>
                {loading ? <Spinner size={16} /> : "Process Return"}
              </Button>
            </div>
          </div>
        )}

        {step === "success" && (
          <div style={{ textAlign: "center", padding: spacing.lg }}>
            <div style={{ fontSize: "48px", marginBottom: spacing.md }}>&#10003;</div>
            <h3 style={{ margin: `0 0 ${spacing.sm}`, color: colors.textPrimary }}>Return Processed</h3>
            <p style={{ color: colors.textSecondary, marginBottom: spacing.lg }}>
              Refund of <strong>${refundAmount.toFixed(2)}</strong> has been issued and inventory restored.
            </p>
            <Button variant="primary" onClick={onClose} fullWidth>Done</Button>
          </div>
        )}
      </div>
    </div>
  );
}
