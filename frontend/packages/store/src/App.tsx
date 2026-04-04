import { Routes, Route, Link } from "react-router-dom";
import { ShopPage } from "./pages/ShopPage";
import { CartCheckoutPage } from "./pages/CartCheckoutPage";
import { OrderStatusPage } from "./pages/OrderStatusPage";
import { AccountPage } from "./pages/AccountPage";
import { CartProvider, useCart } from "./store/cartStore";
import { baseStyles, colors } from "@openmarket/shared";

function NavBar() {
  const { items } = useCart();
  const count = items.reduce((s, i) => s + i.quantity, 0);
  return (
    <nav style={baseStyles.nav}>
      <Link to="/" style={baseStyles.navBrand}>OpenMarket</Link>
      <div style={{ flex: 1 }} />
      <Link to="/" style={baseStyles.navLink}>Shop</Link>
      <Link to="/cart" style={{ ...baseStyles.navLink, position: "relative" as const }}>
        Cart
        {count > 0 && (
          <span style={{
            position: "absolute", top: -8, right: -14,
            background: colors.brand, color: "#fff",
            borderRadius: "50%", width: 18, height: 18,
            fontSize: 11, fontWeight: 700,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>{count}</span>
        )}
      </Link>
      <Link to="/order-status" style={baseStyles.navLink}>Track Order</Link>
      <Link to="/account" style={baseStyles.navLink}>Account</Link>
    </nav>
  );
}

export function App() {
  return (
    <CartProvider>
      <div style={baseStyles.page}>
        <NavBar />
        <Routes>
          <Route path="/" element={<ShopPage />} />
          <Route path="/cart" element={<CartCheckoutPage />} />
          <Route path="/order-status" element={<OrderStatusPage />} />
          <Route path="/account" element={<AccountPage />} />
        </Routes>
      </div>
    </CartProvider>
  );
}
