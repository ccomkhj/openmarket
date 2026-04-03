import { useEffect, useState } from "react";
import { api } from "@openmarket/shared";
import type { Order, OrderListItem } from "@openmarket/shared";

export function OrdersPage() {
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [tab, setTab] = useState<"unfulfilled" | "fulfilled">("unfulfilled");
  const [expandedOrder, setExpandedOrder] = useState<Order | null>(null);

  const loadOrders = async () => { setOrders(await api.orders.list({ fulfillment_status: tab })); };
  useEffect(() => { loadOrders(); }, [tab]);

  const expandOrder = async (id: number) => {
    if (expandedOrder?.id === id) { setExpandedOrder(null); return; }
    setExpandedOrder(await api.orders.get(id));
  };

  const fulfill = async (orderId: number) => {
    await api.fulfillments.create(orderId, { status: "delivered" });
    await loadOrders();
    setExpandedOrder(null);
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Orders</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button onClick={() => setTab("unfulfilled")} style={{ fontWeight: tab === "unfulfilled" ? "bold" : "normal" }}>Unfulfilled</button>
        <button onClick={() => setTab("fulfilled")} style={{ fontWeight: tab === "fulfilled" ? "bold" : "normal" }}>Fulfilled</button>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr style={{ borderBottom: "2px solid #333", textAlign: "left" }}>
          <th style={{ padding: "0.5rem" }}>Order #</th><th>Source</th><th>Total</th><th>Date</th><th>Status</th>
        </tr></thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}>
              <td colSpan={5} style={{ padding: 0 }}>
                <div onClick={() => expandOrder(o.id)} style={{ display: "flex", cursor: "pointer", padding: "0.5rem", borderBottom: "1px solid #eee" }}>
                  <span style={{ flex: 1 }}>{o.order_number}</span>
                  <span style={{ flex: 1 }}>{o.source}</span>
                  <span style={{ flex: 1 }}>${o.total_price}</span>
                  <span style={{ flex: 1 }}>{new Date(o.created_at).toLocaleDateString()}</span>
                  <span style={{ flex: 1 }}>{o.fulfillment_status}</span>
                </div>
                {expandedOrder?.id === o.id && (
                  <div style={{ padding: "1rem", background: "#f5f5f5" }}>
                    <h4>Line Items</h4>
                    <ul>{expandedOrder.line_items.map((li) => (<li key={li.id}>{li.title} x{li.quantity} @ ${li.price}</li>))}</ul>
                    {expandedOrder.shipping_address && (
                      <><h4>Shipping Address</h4><p>{expandedOrder.shipping_address.address1}, {expandedOrder.shipping_address.city} {expandedOrder.shipping_address.zip}</p></>
                    )}
                    {expandedOrder.fulfillment_status === "unfulfilled" && (
                      <button onClick={() => fulfill(o.id)} style={{ marginTop: "0.5rem" }}>Mark as Fulfilled</button>
                    )}
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
