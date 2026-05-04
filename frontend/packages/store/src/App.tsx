import { Routes, Route, Link } from "react-router-dom";
import { ShopPage } from "./pages/ShopPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { CartCheckoutPage } from "./pages/CartCheckoutPage";
import { OrderStatusPage } from "./pages/OrderStatusPage";
import { AccountPage } from "./pages/AccountPage";
import { CartProvider, useCart } from "./store/cartStore";
import { baseStyles, colors, spacing, ToastProvider } from "@openmarket/shared";
import { useIsMobile } from "./hooks/useIsMobile";

function NavBar() {
  const { items } = useCart();
  const count = items.reduce((s, i) => s + i.quantity, 0);
  const isMobile = useIsMobile();

  const navStyle = {
    ...baseStyles.nav,
    padding: isMobile ? `0 ${spacing.md}` : `0 ${spacing.lg}`,
    gap: isMobile ? spacing.sm : spacing.lg,
  };
  const linkStyle = {
    ...baseStyles.navLink,
    fontSize: isMobile ? "0.85rem" : "0.9rem",
  };

  return (
    <nav style={navStyle}>
      <Link to="/" style={baseStyles.navBrand}>OpenMarket</Link>
      <div style={{ flex: 1 }} />
      {!isMobile && <Link to="/" style={linkStyle}>Shop</Link>}
      <Link to="/cart" style={{ ...linkStyle, position: "relative" as const }}>
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
      <Link to="/order-status" style={linkStyle}>{isMobile ? "Track" : "Track Order"}</Link>
      <Link to="/account" style={linkStyle}>Account</Link>
    </nav>
  );
}

export function App() {
  return (
    <ToastProvider>
      <CartProvider>
        <div style={baseStyles.page}>
          <NavBar />
          <Routes>
            <Route path="/" element={<ShopPage />} />
            <Route path="/product/:id" element={<ProductDetailPage />} />
            <Route path="/cart" element={<CartCheckoutPage />} />
            <Route path="/order-status" element={<OrderStatusPage />} />
            <Route path="/account" element={<AccountPage />} />
          </Routes>
        </div>
      </CartProvider>
    </ToastProvider>
  );
}
