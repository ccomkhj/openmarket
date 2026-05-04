import { useEffect, useState } from "react";
import { Routes, Route, Link, Navigate, useLocation } from "react-router-dom";
import { ProductsInventoryPage } from "./pages/ProductsInventoryPage";
import { OrdersPage } from "./pages/OrdersPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { CustomersPage } from "./pages/CustomersPage";
import { SettingsPage } from "./pages/SettingsPage";
import { Security } from "./pages/Security";
import { Users } from "./pages/Users";
import { ZReport } from "./pages/ZReport";
import { DsfinvkExport } from "./pages/DsfinvkExport";
import { RecentSales } from "./pages/RecentSales";
import { api, baseStyles, colors, ToastProvider, type Me } from "@openmarket/shared";
import { RequireAuth } from "./components/RequireAuth";
import { CommandPalette, COMMAND_PALETTE_HINT } from "./components/CommandPalette";

export function App() {
  return (
    <RequireAuth>
      {(me) => <AdminShell me={me} />}
    </RequireAuth>
  );
}

function AdminShell({ me }: { me: Me }) {
  const location = useLocation();
  const [unfulfilled, setUnfulfilled] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => api.orders.unfulfilledCount()
      .then((r) => { if (!cancelled) setUnfulfilled(r.count); })
      .catch(() => { if (!cancelled) setUnfulfilled(null); });
    load();
    const id = setInterval(load, 60_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const linkStyle = (path: string) => ({
    ...baseStyles.navLink,
    color: location.pathname === path ? colors.brand : colors.textSecondary,
    fontWeight: location.pathname === path ? (600 as const) : (500 as const),
  });

  const badgeStyle: React.CSSProperties = {
    marginLeft: 6, padding: "1px 7px", borderRadius: 10,
    background: colors.danger, color: "#fff",
    fontSize: 11, fontWeight: 700, verticalAlign: "middle",
  };

  const canSeeSecurity = me.role === "owner" || me.role === "manager";
  const canSeeUsers = me.role === "owner";
  const canSeeZReport = me.role === "owner" || me.role === "manager";
  const canSeeDsfinvk = me.role === "owner";
  const canSeeSales = me.role === "owner" || me.role === "manager";

  return (
  <ToastProvider>
    <CommandPalette />
    <div style={baseStyles.page}>
      <nav style={baseStyles.nav}>
        <span style={{ ...baseStyles.navBrand, cursor: "default" }}>OpenMarket Admin</span>
        <div style={{ flex: 1 }} />
        <span style={{
          fontSize: 12, color: colors.textSecondary,
          border: `1px solid ${colors.border}`, borderRadius: 4,
          padding: "2px 8px", marginRight: 8,
        }} title="Open command palette">{COMMAND_PALETTE_HINT} Search</span>
        <Link to="/analytics" style={linkStyle("/analytics")}>Analytics</Link>
        <Link to="/products" style={linkStyle("/products")}>Products & Inventory</Link>
        <Link to="/orders" style={linkStyle("/orders")}>
          Orders
          {unfulfilled !== null && unfulfilled > 0 && <span style={badgeStyle}>{unfulfilled}</span>}
        </Link>
        <Link to="/customers" style={linkStyle("/customers")}>Customers</Link>
        <Link to="/settings" style={linkStyle("/settings")}>Settings</Link>
        {canSeeSecurity && (
          <Link to="/security" style={linkStyle("/security")}>Security</Link>
        )}
        {canSeeUsers && (
          <Link to="/users" style={linkStyle("/users")}>Users</Link>
        )}
        {canSeeSales && (
          <Link to="/sales" style={linkStyle("/sales")}>Sales</Link>
        )}
        {canSeeZReport && (
          <Link to="/z-report" style={linkStyle("/z-report")}>Z-Report</Link>
        )}
        {canSeeDsfinvk && (
          <Link to="/dsfinvk" style={linkStyle("/dsfinvk")}>DSFinV-K</Link>
        )}
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/analytics" replace />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/products" element={<ProductsInventoryPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/security" element={<Security />} />
        <Route path="/users" element={<Users />} />
        <Route path="/sales" element={<RecentSales />} />
        <Route path="/z-report" element={<ZReport />} />
        <Route path="/dsfinvk" element={<DsfinvkExport />} />
      </Routes>
    </div>
  </ToastProvider>
  );
}
