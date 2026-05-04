import { useEffect, useState } from "react";
import { api, useDebounce, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import { useQueryParam } from "../hooks/useQueryParam";
import type { Customer, OrderListItem } from "@openmarket/shared";

export function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useQueryParam("q");
  const debouncedSearch = useDebounce(search, 300);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedOrders, setExpandedOrders] = useState<OrderListItem[]>([]);

  useEffect(() => {
    setLoading(true);
    api.customers.list({ search: debouncedSearch || undefined })
      .then(setCustomers)
      .finally(() => setLoading(false));
  }, [debouncedSearch]);

  const expand = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    setExpandedOrders(await api.customers.orders(id));
  };

  return (
    <div style={baseStyles.container}>
      <h2 style={{ marginBottom: spacing.lg }}>Customers</h2>
      <input placeholder="Search by name, email, or phone..." value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ ...baseStyles.input, marginBottom: spacing.lg }} />

      {loading ? <Spinner label="Loading customers..." /> : customers.length === 0 ? (
        <div style={{ ...baseStyles.card, textAlign: "center", padding: spacing.xl, color: colors.textSecondary }}>
          {search ? "No customers match your search" : "No customers yet"}
        </div>
      ) : (
        <div style={{ ...baseStyles.card, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
            <thead>
              <tr style={{ background: colors.surfaceMuted, textAlign: "left" }}>
                <th style={{ padding: "10px 16px" }}>Name</th>
                <th style={{ padding: "10px 16px" }}>Email</th>
                <th style={{ padding: "10px 16px" }}>Phone</th>
                <th style={{ padding: "10px 16px" }}>Addresses</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tbody key={c.id}>
                  <tr onClick={() => expand(c.id)} style={{ cursor: "pointer", borderBottom: `1px solid ${colors.border}`, background: expandedId === c.id ? colors.surfaceMuted : colors.surface }}>
                    <td style={{ padding: "10px 16px", fontWeight: 500 }}>{c.first_name} {c.last_name}</td>
                    <td style={{ padding: "10px 16px", color: colors.textSecondary }}>{c.email || "---"}</td>
                    <td style={{ padding: "10px 16px" }}>{c.phone || "---"}</td>
                    <td style={{ padding: "10px 16px", color: colors.textSecondary }}>{c.addresses.length}</td>
                  </tr>
                  {expandedId === c.id && (
                    <tr>
                      <td colSpan={4} style={{ padding: "16px", background: colors.surfaceMuted, borderBottom: `1px solid ${colors.border}` }}>
                        {c.addresses.length > 0 && (
                          <div style={{ marginBottom: spacing.md }}>
                            <strong style={{ fontSize: "13px", color: colors.textSecondary }}>Addresses</strong>
                            {c.addresses.map((a) => (
                              <div key={a.id} style={{ fontSize: "13px", marginTop: "4px" }}>
                                {a.address1}, {a.city} {a.zip} {a.is_default && <span style={{ color: colors.brand, fontSize: "11px" }}>(default)</span>}
                              </div>
                            ))}
                          </div>
                        )}
                        <strong style={{ fontSize: "13px", color: colors.textSecondary }}>Order History ({expandedOrders.length})</strong>
                        {expandedOrders.length === 0 ? (
                          <div style={{ fontSize: "13px", color: colors.textSecondary, marginTop: "4px" }}>No orders</div>
                        ) : (
                          <div style={{ marginTop: "4px" }}>
                            {expandedOrders.map((o) => (
                              <div key={o.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", padding: "4px 0" }}>
                                <span>{o.order_number}</span>
                                <span>${o.total_price} &middot; {o.fulfillment_status}</span>
                              </div>
                            ))}
                          </div>
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
