import { useState } from "react";
import type { CSSProperties } from "react";
import { api, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Customer, OrderListItem } from "@openmarket/shared";
import { usePageMeta } from "../hooks/usePageMeta";

function fulfillmentBadgeStyle(status: string): CSSProperties {
  const fulfilled = status === "fulfilled";
  const pending = status === "pending";
  return {
    padding: "4px 10px",
    borderRadius: radius.sm,
    fontSize: "12px",
    fontWeight: 600,
    textTransform: "uppercase" as const,
    background: fulfilled ? colors.successSurface : pending ? colors.warningSurface : colors.surface,
    color: fulfilled ? colors.success : pending ? colors.warning : colors.textSecondary,
  };
}

export function AccountPage() {
  usePageMeta("Account", "Look up your account and orders.");
  const [phone, setPhone] = useState("");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const lookup = async () => {
    if (!phone.trim()) return;
    setLoading(true);
    setError("");
    setCustomer(null);
    setOrders([]);
    try {
      const found = await api.customers.lookup({ phone: phone.trim() });
      setCustomer(found);
      const customerOrders = await api.customers.orders(found.id);
      setOrders(customerOrders);
    } catch {
      setError("No account found for that phone number. Please check and try again.");
    } finally {
      setLoading(false);
    }
  };

  const signOut = () => {
    setCustomer(null);
    setOrders([]);
    setPhone("");
    setError("");
  };

  return (
    <div style={{ ...baseStyles.container, maxWidth: 600 }}>
      <h2 style={{ marginBottom: spacing.lg }}>My Account</h2>

      {!customer && (
        <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
          <p style={{ fontSize: "14px", color: colors.textSecondary, marginTop: 0, marginBottom: spacing.md }}>
            Enter your phone number to look up your account and order history.
          </p>
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              placeholder="Phone number (e.g. +1 555-555-5555)"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && lookup()}
              style={baseStyles.input}
            />
            <Button variant="primary" onClick={lookup} loading={loading} style={{ flexShrink: 0 }}>
              Look Up
            </Button>
          </div>
          {error && (
            <div style={{
              background: colors.dangerSurface,
              color: colors.danger,
              padding: "8px 12px",
              borderRadius: radius.sm,
              fontSize: "14px",
              marginTop: "10px",
            }}>
              {error}
            </div>
          )}
        </div>
      )}

      {loading && <Spinner label="Looking up account..." />}

      {customer && (
        <>
          <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: spacing.md }}>
              <h3 style={{ margin: 0, fontSize: "16px" }}>
                {customer.first_name} {customer.last_name}
              </h3>
              <Button variant="secondary" onClick={signOut}>Sign Out</Button>
            </div>
            <div style={{ fontSize: "14px", color: colors.textSecondary, display: "flex", flexDirection: "column", gap: "4px" }}>
              {customer.email && <span>Email: {customer.email}</span>}
              <span>Phone: {customer.phone}</span>
            </div>
          </div>

          <h3 style={{ marginBottom: spacing.md }}>Order History</h3>

          {orders.length === 0 ? (
            <div style={{ ...baseStyles.card, color: colors.textSecondary, fontSize: "14px" }}>
              No orders found for this account.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: spacing.sm }}>
              {orders.map((order) => (
                <div key={order.id} style={baseStyles.card}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                    <span style={{ fontWeight: 600, fontSize: "15px" }}>Order {order.order_number}</span>
                    <span style={fulfillmentBadgeStyle(order.fulfillment_status)}>{order.fulfillment_status}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "14px", color: colors.textSecondary }}>
                    <span>{new Date(order.created_at).toLocaleDateString()}</span>
                    <span style={{ fontWeight: 600, color: colors.textPrimary }}>${order.total_price}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
