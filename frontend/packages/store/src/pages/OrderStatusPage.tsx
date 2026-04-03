import { useState } from "react";
import { api, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Order } from "@openmarket/shared";

export function OrderStatusPage() {
  const [orderNumber, setOrderNumber] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const lookup = async () => {
    if (!orderNumber.trim()) return;
    setLoading(true); setError(""); setOrder(null);
    try {
      const found = await api.orders.lookup(orderNumber.trim());
      setOrder(found);
    } catch { setError("Order not found. Please check the order number and try again."); }
    finally { setLoading(false); }
  };

  return (
    <div style={{ ...baseStyles.container, maxWidth: 600 }}>
      <h2 style={{ marginBottom: spacing.lg }}>Track Your Order</h2>
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <div style={{ display: "flex", gap: "8px" }}>
          <input placeholder="Enter order number (e.g. ORD-...)" value={orderNumber}
            onChange={(e) => setOrderNumber(e.target.value)} onKeyDown={(e) => e.key === "Enter" && lookup()}
            style={baseStyles.input} />
          <Button variant="primary" onClick={lookup} loading={loading} style={{ flexShrink: 0 }}>Look Up</Button>
        </div>
        {error && <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px", marginTop: "10px" }}>{error}</div>}
      </div>

      {loading && <Spinner label="Looking up order..." />}

      {order && (
        <div style={baseStyles.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
            <h3 style={{ margin: 0, fontSize: "16px" }}>Order {order.order_number}</h3>
            <span style={{
              padding: "4px 10px", borderRadius: radius.sm, fontSize: "12px", fontWeight: 600, textTransform: "uppercase",
              background: order.fulfillment_status === "fulfilled" ? colors.successSurface : colors.warningSurface,
              color: order.fulfillment_status === "fulfilled" ? colors.success : colors.warning,
            }}>{order.fulfillment_status}</span>
          </div>
          <div style={{ fontSize: "14px", color: colors.textSecondary, marginBottom: spacing.md }}>Placed {new Date(order.created_at).toLocaleString()}</div>
          <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: spacing.md }}>
            {order.line_items.map((li) => (
              <div key={li.id} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: "14px" }}>
                <span>{li.title} &times; {li.quantity}</span>
                <span style={{ fontWeight: 600 }}>${(parseFloat(li.price) * li.quantity).toFixed(2)}</span>
              </div>
            ))}
            <div style={{ display: "flex", justifyContent: "space-between", borderTop: `1px solid ${colors.border}`, paddingTop: "8px", marginTop: "8px", fontWeight: 700 }}>
              <span>Total</span><span>${order.total_price}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
