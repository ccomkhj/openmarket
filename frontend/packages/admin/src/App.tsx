import { Routes, Route, Link, Navigate, useLocation } from "react-router-dom";
import { ProductsInventoryPage } from "./pages/ProductsInventoryPage";
import { OrdersPage } from "./pages/OrdersPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { CustomersPage } from "./pages/CustomersPage";
import { baseStyles, colors } from "@openmarket/shared";

export function App() {
  const location = useLocation();
  const linkStyle = (path: string) => ({
    ...baseStyles.navLink,
    color: location.pathname === path ? colors.brand : colors.textSecondary,
    fontWeight: location.pathname === path ? (600 as const) : (500 as const),
  });

  return (
    <div style={baseStyles.page}>
      <nav style={baseStyles.nav}>
        <span style={{ ...baseStyles.navBrand, cursor: "default" }}>OpenMarket Admin</span>
        <div style={{ flex: 1 }} />
        <Link to="/analytics" style={linkStyle("/analytics")}>Analytics</Link>
        <Link to="/products" style={linkStyle("/products")}>Products & Inventory</Link>
        <Link to="/orders" style={linkStyle("/orders")}>Orders</Link>
        <Link to="/customers" style={linkStyle("/customers")}>Customers</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/analytics" replace />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/products" element={<ProductsInventoryPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/customers" element={<CustomersPage />} />
      </Routes>
    </div>
  );
}
