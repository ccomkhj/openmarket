import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Button, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

export function CartCheckoutPage() {
  const { items, updateQuantity, removeItem, clearCart, total } = useCart();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [zip, setZip] = useState("");
  const [discountCode, setDiscountCode] = useState("");
  const [discount, setDiscount] = useState<{ type: string; value: number } | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [orderNumber, setOrderNumber] = useState("");

  const applyDiscount = async () => {
    try {
      const d = await api.discounts.lookup(discountCode);
      setDiscount({ type: d.discount_type, value: parseFloat(d.value) });
      setError("");
    } catch { setError("Invalid or expired discount code"); setDiscount(null); }
  };

  const finalTotal = discount
    ? discount.type === "percentage" ? total * (1 - discount.value / 100) : Math.max(0, total - discount.value)
    : total;

  const canSubmit = name && phone && address && city && zip && items.length > 0 && !submitting;

  const placeOrder = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError("");
    try {
      const order = await api.orders.create({
        source: "web", customer_name: name, customer_phone: phone,
        shipping_address: { address1: address, city, zip },
        line_items: items.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
      });
      setOrderNumber(order.order_number);
      clearCart();
    } catch (e: any) { setError(e.message || "Failed to place order"); }
    finally { setSubmitting(false); }
  };

  if (orderNumber) {
    return (
      <div style={{ ...baseStyles.container, maxWidth: 500, textAlign: "center", paddingTop: spacing.xl }}>
        <div style={baseStyles.card}>
          <div style={{ fontSize: "40px", marginBottom: spacing.md }}>&#10003;</div>
          <h2 style={{ margin: "0 0 8px" }}>Order Placed!</h2>
          <p style={{ color: colors.textSecondary }}>Your order number is:</p>
          <p style={{ fontSize: "20px", fontWeight: 700, color: colors.brand, margin: "8px 0 24px" }}>{orderNumber}</p>
          <p style={{ color: colors.textSecondary, fontSize: "14px", marginBottom: spacing.lg }}>Payment will be collected on delivery.</p>
          <Button variant="primary" onClick={() => navigate("/order-status")}>Track Order</Button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ ...baseStyles.container, maxWidth: 600 }}>
      <h2 style={{ marginBottom: spacing.lg }}>Cart</h2>
      {items.length === 0 ? (
        <div style={{ ...baseStyles.card, textAlign: "center", padding: spacing.xl }}>
          <p style={{ color: colors.textSecondary, fontSize: "16px" }}>Your cart is empty</p>
          <Button variant="primary" onClick={() => navigate("/")} style={{ marginTop: spacing.md }}>Browse Products</Button>
        </div>
      ) : (
        <>
          <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
            {items.map((item, i) => (
              <div key={item.variant.id} style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "12px 0", borderBottom: i < items.length - 1 ? `1px solid ${colors.border}` : undefined,
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.product.title}</div>
                  <div style={{ color: colors.textSecondary, fontSize: "13px" }}>{item.variant.title} &middot; ${item.variant.price}</div>
                </div>
                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <Button variant="secondary" size="sm" onClick={() => updateQuantity(item.variant.id, item.quantity - 1)}>-</Button>
                  <span style={{ width: 28, textAlign: "center", fontWeight: 600 }}>{item.quantity}</span>
                  <Button variant="secondary" size="sm" onClick={() => updateQuantity(item.variant.id, item.quantity + 1)}>+</Button>
                  <Button variant="danger" size="sm" onClick={() => removeItem(item.variant.id)}>Remove</Button>
                </div>
              </div>
            ))}
          </div>

          <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
            <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
              <input placeholder="Discount code" value={discountCode} onChange={(e) => setDiscountCode(e.target.value)} style={baseStyles.input} />
              <Button variant="secondary" onClick={applyDiscount} style={{ flexShrink: 0 }}>Apply</Button>
            </div>
            {discount && (
              <div style={{ background: colors.successSurface, color: colors.success, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px" }}>
                Discount applied: {discount.type === "percentage" ? `${discount.value}%` : `$${discount.value}`} off
              </div>
            )}
            <div style={{ fontSize: "20px", fontWeight: 700, textAlign: "right", marginTop: spacing.md }}>Total: ${finalTotal.toFixed(2)}</div>
          </div>

          <div style={baseStyles.card}>
            <h3 style={{ margin: "0 0 16px", fontSize: "16px" }}>Delivery Details</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <input placeholder="Full name *" value={name} onChange={(e) => setName(e.target.value)} style={baseStyles.input} />
              <input placeholder="Phone *" value={phone} onChange={(e) => setPhone(e.target.value)} style={baseStyles.input} />
              <input placeholder="Address *" value={address} onChange={(e) => setAddress(e.target.value)} style={baseStyles.input} />
              <div style={{ display: "flex", gap: "10px" }}>
                <input placeholder="City *" value={city} onChange={(e) => setCity(e.target.value)} style={baseStyles.input} />
                <input placeholder="ZIP *" value={zip} onChange={(e) => setZip(e.target.value)} style={{ ...baseStyles.input, maxWidth: 120 }} />
              </div>
            </div>
            <p style={{ color: colors.textSecondary, fontSize: "13px", margin: "12px 0 4px" }}>Payment will be collected on delivery.</p>
            {error && <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "8px 12px", borderRadius: radius.sm, fontSize: "14px", marginTop: "8px" }}>{error}</div>}
            <Button variant="primary" size="lg" fullWidth loading={submitting} disabled={!canSubmit} onClick={placeOrder} style={{ marginTop: spacing.md }}>
              Place Order — ${finalTotal.toFixed(2)}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
