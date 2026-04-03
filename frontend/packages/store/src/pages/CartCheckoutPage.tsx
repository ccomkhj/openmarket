import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@openmarket/shared";
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

  const placeOrder = async () => {
    try {
      const order = await api.orders.create({
        source: "web",
        customer_name: name, customer_phone: phone,
        shipping_address: { address1: address, city, zip },
        line_items: items.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
      });
      setOrderNumber(order.order_number);
      clearCart();
    } catch (e: any) { setError(e.message); }
  };

  if (orderNumber) {
    return (
      <div style={{ padding: "2rem", textAlign: "center" }}>
        <h2>Order Placed!</h2>
        <p>Your order number is: <strong>{orderNumber}</strong></p>
        <button onClick={() => navigate("/order-status")}>Track Order</button>
      </div>
    );
  }

  return (
    <div style={{ padding: "1rem", maxWidth: 600, margin: "0 auto" }}>
      <h2>Cart</h2>
      {items.length === 0 ? <p>Your cart is empty</p> : (
        <>
          {items.map((item) => (
            <div key={item.variant.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.5rem 0", borderBottom: "1px solid #eee" }}>
              <div><strong>{item.product.title}</strong> - {item.variant.title}<br />${item.variant.price} each</div>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <button onClick={() => updateQuantity(item.variant.id, item.quantity - 1)}>-</button>
                <span>{item.quantity}</span>
                <button onClick={() => updateQuantity(item.variant.id, item.quantity + 1)}>+</button>
                <button onClick={() => removeItem(item.variant.id)}>Remove</button>
              </div>
            </div>
          ))}
          <div style={{ margin: "1rem 0", display: "flex", gap: "0.5rem" }}>
            <input placeholder="Discount code" value={discountCode} onChange={(e) => setDiscountCode(e.target.value)} />
            <button onClick={applyDiscount}>Apply</button>
          </div>
          {discount && <p>Discount applied: {discount.type === "percentage" ? `${discount.value}%` : `$${discount.value}`} off</p>}
          <p style={{ fontSize: "1.2rem", fontWeight: "bold" }}>Total: ${finalTotal.toFixed(2)}</p>
          <h3>Delivery Details</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <input placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} />
            <input placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <input placeholder="Address" value={address} onChange={(e) => setAddress(e.target.value)} />
            <input placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
            <input placeholder="ZIP code" value={zip} onChange={(e) => setZip(e.target.value)} />
          </div>
          {error && <p style={{ color: "red" }}>{error}</p>}
          <button onClick={placeOrder} disabled={!name || !phone || !address} style={{ marginTop: "1rem", padding: "0.75rem 2rem" }}>Place Order</button>
        </>
      )}
    </div>
  );
}
