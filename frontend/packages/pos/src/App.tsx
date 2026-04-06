import { useState, useEffect } from "react";
import { SalePage } from "./pages/SalePage";
import { font, colors, spacing, baseStyles, ToastProvider } from "@openmarket/shared";

function Clock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return <span>{time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>;
}

export function App() {
  return (
    <ToastProvider>
      <div style={{ fontFamily: font.body, display: "flex", flexDirection: "column", height: "100vh" }}>
        <nav style={{
          ...baseStyles.nav,
          height: "44px",
          padding: `0 ${spacing.md}`,
          borderBottom: `1px solid ${colors.border}`,
          justifyContent: "space-between",
        }}>
          <span style={{ fontWeight: 700, color: colors.brand, fontSize: "1rem" }}>OpenMarket POS</span>
          <div style={{ display: "flex", alignItems: "center", gap: spacing.lg, fontSize: "13px", color: colors.textSecondary }}>
            <Clock />
            <span>{new Date().toLocaleDateString()}</span>
          </div>
        </nav>
        <div style={{ flex: 1, overflow: "hidden" }}>
          <SalePage />
        </div>
      </div>
    </ToastProvider>
  );
}
