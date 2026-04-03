import { Routes, Route, Link, Navigate } from "react-router-dom";
import { ProductsInventoryPage } from "./pages/ProductsInventoryPage";
import { OrdersPage } from "./pages/OrdersPage";

export function App() {
  return (
    <div>
      <nav style={{ padding: "1rem", borderBottom: "1px solid #eee", display: "flex", gap: "1rem", alignItems: "center" }}>
        <strong style={{ fontSize: "1.2rem" }}>OpenMarket Admin</strong>
        <Link to="/products">Products & Inventory</Link>
        <Link to="/orders">Orders</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/products" replace />} />
        <Route path="/products" element={<ProductsInventoryPage />} />
        <Route path="/orders" element={<OrdersPage />} />
      </Routes>
    </div>
  );
}
