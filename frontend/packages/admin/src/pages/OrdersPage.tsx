import { useEffect, useState } from "react";
import { api, useDebounce, exportCsv, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Order, OrderListItem } from "@openmarket/shared";

export function OrdersPage() {
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"unfulfilled" | "fulfilled">("unfulfilled");
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const debouncedSearch = useDebounce(search, 300);
  const [expandedOrder, setExpandedOrder] = useState<Order | null>(null);

  const loadOrders = async () => {
    setLoading(true);
    setOrders(await api.orders.list({
      fulfillment_status: tab,
      search: debouncedSearch || undefined,
      source: sourceFilter || undefined,
    }));
    setLoading(false);
  };

  useEffect(() => { loadOrders(); }, [tab, debouncedSearch, sourceFilter]);

  const expandOrder = async (id: number) => {
    if (expandedOrder?.id === id) { setExpandedOrder(null); return; }
    setExpandedOrder(await api.orders.get(id));
  };

  const fulfill = async (orderId: number) => {
    await api.fulfillments.create(orderId, { status: "delivered" });
    await loadOrders();
    setExpandedOrder(null);
  };

  const handleExport = () => {
    exportCsv(
      `orders-${tab}-${new Date().toISOString().slice(0, 10)}.csv`,
      ["Order #", "Source", "Total", "Date", "Status"],
      orders.map((o) => [o.order_number, o.source, `$${o.total_price}`, new Date(o.created_at).toLocaleDateString(), o.fulfillment_status]),
    );
  };

  const tabStyle = (active: boolean) => ({
    padding: "7px 16px", borderRadius: radius.sm, fontSize: "14px",
    fontWeight: active ? (600 as const) : (400 as const),
    background: active ? colors.brand : "transparent",
    color: active ? "#fff" : colors.textPrimary,
    border: `1px solid ${active ? colors.brand : colors.borderStrong}`,
    cursor: "pointer" as const,
  });

  return (
    <div style={baseStyles.container}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
        <h2 style={{ margin: 0 }}>Orders</h2>
        <Button variant="secondary" size="sm" onClick={handleExport} disabled={orders.length === 0}>Export CSV</Button>
      </div>

      <div style={{ display: "flex", gap: spacing.sm, marginBottom: spacing.lg, flexWrap: "wrap" }}>
        <button onClick={() => setTab("unfulfilled")} style={tabStyle(tab === "unfulfilled")}>Unfulfilled</button>
        <button onClick={() => setTab("fulfilled")} style={tabStyle(tab === "fulfilled")}>Fulfilled</button>
        <div style={{ flex: 1 }} />
        <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}
          style={{ ...baseStyles.input, width: "auto", minWidth: 100 }}>
          <option value="">All Sources</option>
          <option value="web">Web</option>
          <option value="pos">POS</option>
        </select>
        <input placeholder="Search order #..." value={search} onChange={(e) => setSearch(e.target.value)}
          style={{ ...baseStyles.input, width: 200 }} />
      </div>

      {loading ? <Spinner label="Loading orders..." /> : orders.length === 0 ? (
        <div style={{ ...baseStyles.card, textAlign: "center", padding: spacing.xl, color: colors.textSecondary }}>
          No {tab} orders{search && " matching your search"}
        </div>
      ) : (
        <div style={{ ...baseStyles.card, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
            <thead>
              <tr style={{ background: colors.surfaceMuted, textAlign: "left" }}>
                <th style={{ padding: "10px 16px" }}>Order #</th>
                <th style={{ padding: "10px 16px" }}>Source</th>
                <th style={{ padding: "10px 16px" }}>Total</th>
                <th style={{ padding: "10px 16px" }}>Date</th>
                <th style={{ padding: "10px 16px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tbody key={o.id}>
                  <tr onClick={() => expandOrder(o.id)} style={{ cursor: "pointer", borderBottom: `1px solid ${colors.border}`, background: expandedOrder?.id === o.id ? colors.surfaceMuted : colors.surface }}>
                    <td style={{ padding: "10px 16px", fontWeight: 500 }}>{o.order_number}</td>
                    <td style={{ padding: "10px 16px" }}>
                      <span style={{ padding: "2px 8px", borderRadius: "4px", fontSize: "12px", fontWeight: 600, background: o.source === "pos" ? colors.brandLight : colors.warningSurface, color: o.source === "pos" ? colors.brand : colors.warning }}>
                        {o.source.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: "10px 16px" }}>${o.total_price}</td>
                    <td style={{ padding: "10px 16px", color: colors.textSecondary }}>{new Date(o.created_at).toLocaleDateString()}</td>
                    <td style={{ padding: "10px 16px" }}>{o.fulfillment_status}</td>
                  </tr>
                  {expandedOrder?.id === o.id && (
                    <tr>
                      <td colSpan={5} style={{ padding: "16px", background: colors.surfaceMuted, borderBottom: `1px solid ${colors.border}` }}>
                        <div style={{ fontSize: "13px" }}>
                          {expandedOrder.line_items.map((li) => (
                            <div key={li.id} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                              <span>{li.title} &times; {li.quantity}</span>
                              <span>${(parseFloat(li.price) * li.quantity).toFixed(2)}</span>
                            </div>
                          ))}
                        </div>
                        {expandedOrder.shipping_address && (
                          <div style={{ marginTop: "12px", fontSize: "13px", color: colors.textSecondary }}>
                            Deliver to: {expandedOrder.shipping_address.address1}, {expandedOrder.shipping_address.city} {expandedOrder.shipping_address.zip}
                          </div>
                        )}
                        {expandedOrder.fulfillment_status === "unfulfilled" && (
                          <Button variant="primary" size="sm" onClick={() => fulfill(o.id)} style={{ marginTop: "12px" }}>
                            Mark as Fulfilled
                          </Button>
                        )}
                      </td>
                    </tr>
                  )}
                </tbody>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
