import { useEffect, useState } from "react";
import { api, Spinner, Button, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { AnalyticsSummary } from "@openmarket/shared";

export function AnalyticsPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const loadSummary = async (d: number) => {
    setLoading(true);
    try {
      setSummary(await api.analytics.summary(d));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadSummary(days); }, [days]);

  const periodStyle = (d: number) => ({
    padding: "6px 14px",
    borderRadius: radius.sm,
    fontSize: "13px",
    fontWeight: days === d ? (600 as const) : (400 as const),
    background: days === d ? colors.brand : "transparent",
    color: days === d ? "#fff" : colors.textPrimary,
    border: `1px solid ${days === d ? colors.brand : colors.borderStrong}`,
    cursor: "pointer" as const,
  });

  const metricCard = (label: string, value: string, accent?: string) => (
    <div style={{
      ...baseStyles.card,
      flex: 1,
      padding: spacing.lg,
      borderLeft: `4px solid ${accent ?? colors.border}`,
    }}>
      <div style={{ fontSize: "12px", color: colors.textSecondary, marginBottom: "6px", textTransform: "uppercase" as const, letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: "28px", fontWeight: 700, color: accent ?? colors.textPrimary }}>{value}</div>
    </div>
  );

  const maxRevenue = summary
    ? Math.max(...summary.daily_sales.map((d) => parseFloat(d.revenue)), 1)
    : 1;

  return (
    <div style={baseStyles.container}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.lg }}>
        <h2 style={{ margin: 0 }}>Analytics</h2>
        <div style={{ display: "flex", gap: "8px" }}>
          <button onClick={() => setDays(7)} style={periodStyle(7)}>7d</button>
          <button onClick={() => setDays(30)} style={periodStyle(30)}>30d</button>
          <button onClick={() => setDays(90)} style={periodStyle(90)}>90d</button>
        </div>
      </div>

      {loading ? (
        <Spinner label="Loading analytics..." />
      ) : !summary ? null : (
        <>
          {/* Metric cards */}
          <div style={{ display: "flex", gap: spacing.md, marginBottom: spacing.xl }}>
            {metricCard("Revenue", `$${parseFloat(summary.total_revenue).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, colors.brand)}
            {metricCard("Orders", String(summary.total_orders))}
            {metricCard("Avg Order Value", `$${parseFloat(summary.average_order_value).toFixed(2)}`)}
          </div>

          {/* Daily sales bar chart */}
          <div style={{ ...baseStyles.card, marginBottom: spacing.xl, padding: spacing.lg }}>
            <h3 style={{ margin: `0 0 ${spacing.md} 0`, fontSize: "15px" }}>Daily Sales</h3>
            {summary.daily_sales.length === 0 ? (
              <div style={{ color: colors.textSecondary, fontSize: "14px" }}>No sales data for this period</div>
            ) : (
              <div style={{ display: "flex", alignItems: "flex-end", gap: "4px", height: "120px" }}>
                {summary.daily_sales.map((d) => {
                  const heightPct = (parseFloat(d.revenue) / maxRevenue) * 100;
                  return (
                    <div key={d.date} style={{ display: "flex", flexDirection: "column" as const, alignItems: "center", flex: 1, minWidth: 0 }}>
                      <div
                        title={`${d.date}: $${parseFloat(d.revenue).toFixed(2)} (${d.order_count} orders)`}
                        style={{
                          width: "100%",
                          height: `${Math.max(heightPct, 2)}%`,
                          background: colors.brand,
                          borderRadius: `${radius.sm} ${radius.sm} 0 0`,
                          cursor: "default",
                        }}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div style={{ display: "flex", gap: spacing.xl, alignItems: "flex-start" }}>
            {/* Top products table */}
            <div style={{ ...baseStyles.card, flex: 2, padding: 0, overflow: "hidden" }}>
              <div style={{ padding: `${spacing.md} ${spacing.lg}`, borderBottom: `1px solid ${colors.border}` }}>
                <h3 style={{ margin: 0, fontSize: "15px" }}>Top Products</h3>
              </div>
              {summary.top_products.length === 0 ? (
                <div style={{ padding: spacing.lg, color: colors.textSecondary, fontSize: "14px" }}>No product data</div>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
                  <thead>
                    <tr style={{ background: colors.surfaceMuted, textAlign: "left" }}>
                      <th style={{ padding: "8px 16px" }}>Product</th>
                      <th style={{ padding: "8px 16px" }}>Qty Sold</th>
                      <th style={{ padding: "8px 16px" }}>Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.top_products.map((p, i) => (
                      <tr key={i} style={{ borderTop: `1px solid ${colors.border}` }}>
                        <td style={{ padding: "10px 16px" }}>{p.title}</td>
                        <td style={{ padding: "10px 16px", color: colors.textSecondary }}>{p.quantity_sold}</td>
                        <td style={{ padding: "10px 16px" }}>${parseFloat(p.revenue).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Orders by source */}
            <div style={{ ...baseStyles.card, flex: 1, padding: spacing.lg }}>
              <h3 style={{ margin: `0 0 ${spacing.md} 0`, fontSize: "15px" }}>Orders by Source</h3>
              {Object.keys(summary.orders_by_source).length === 0 ? (
                <div style={{ color: colors.textSecondary, fontSize: "14px" }}>No data</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column" as const, gap: "8px" }}>
                  {Object.entries(summary.orders_by_source).map(([source, count]) => (
                    <div key={source} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{
                        padding: "3px 10px",
                        borderRadius: radius.sm,
                        fontSize: "12px",
                        fontWeight: 600,
                        background: source === "pos" ? colors.brandLight : colors.warningSurface,
                        color: source === "pos" ? colors.brand : colors.warning,
                      }}>
                        {source.toUpperCase()}
                      </span>
                      <span style={{ fontWeight: 600 }}>{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
