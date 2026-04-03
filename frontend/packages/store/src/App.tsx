import { Routes, Route, Link } from "react-router-dom";
import { ShopPage } from "./pages/ShopPage";
import { CartCheckoutPage } from "./pages/CartCheckoutPage";
import { OrderStatusPage } from "./pages/OrderStatusPage";
import { CartProvider } from "./store/cartStore";

export function App() {
  return (
    <CartProvider>
      <nav style={{ padding: "1rem", borderBottom: "1px solid #eee", display: "flex", gap: "1rem", alignItems: "center" }}>
        <Link to="/" style={{ fontWeight: "bold", fontSize: "1.2rem", textDecoration: "none" }}>OpenMarket</Link>
        <Link to="/cart">Cart</Link>
        <Link to="/order-status">Track Order</Link>
      </nav>
      <Routes>
        <Route path="/" element={<ShopPage />} />
        <Route path="/cart" element={<CartCheckoutPage />} />
        <Route path="/order-status" element={<OrderStatusPage />} />
      </Routes>
    </CartProvider>
  );
}
