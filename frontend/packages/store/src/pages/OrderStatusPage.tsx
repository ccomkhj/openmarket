import { useState } from "react";
import { api } from "@openmarket/shared";
import type { Order } from "@openmarket/shared";

export function OrderStatusPage() {
  const [orderNumber, setOrderNumber] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");

  const lookup = async () => {
    setError("");
    try {
      const orders = await api.orders.list();
      const found = orders.find((o) => o.order_number === orderNumber);
      if (!found) { setError("Order not found"); return; }
      const full = await api.orders.get(found.id);
      setOrder(full);
    } catch { setError("Could not look up order"); }
  };

  return (
    <div style={{ padding: "1rem", maxWidth: 600, margin: "0 auto" }}>
      <h2>Track Your Order</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input placeholder="Enter order number (e.g. ORD-...)" value={orderNumber}
          onChange={(e) => setOrderNumber(e.target.value)} style={{ flex: 1, padding: "0.5rem" }} />
        <button onClick={lookup}>Look Up</button>
      </div>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {order && (
        <div style={{ border: "1px solid #ddd", padding: "1rem", borderRadius: "4px" }}>
          <h3>Order {order.order_number}</h3>
          <p><strong>Status:</strong> {order.fulfillment_status}</p>
          <p><strong>Total:</strong> ${order.total_price}</p>
          <p><strong>Placed:</strong> {new Date(order.created_at).toLocaleString()}</p>
          <h4>Items:</h4>
          <ul>{order.line_items.map((li) => (<li key={li.id}>{li.title} x{li.quantity} - ${li.price}</li>))}</ul>
        </div>
      )}
    </div>
  );
}
