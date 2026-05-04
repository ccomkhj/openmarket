import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, Button, ConfirmDialog, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { ShippingMethod, TaxRate } from "@openmarket/shared";
import { useCart } from "../store/cartStore";
import { usePageMeta } from "../hooks/usePageMeta";

function validatePhone(phone: string): string | null {
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 7) return "Phone number must be at least 7 digits";
  return null;
}

function validateZip(zip: string): string | null {
  if (zip.length < 3) return "ZIP code is too short";
  return null;
}

export function CartCheckoutPage() {
  const { items, updateQuantity, removeItem, clearCart, total } = useCart();
  const navigate = useNavigate();
  usePageMeta("Cart", "Review your cart and check out.");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [zip, setZip] = useState("");
  const [discountCode, setDiscountCode] = useState("");
  const [discount, setDiscount] = useState<{ type: string; value: number } | null>(null);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [orderNumber, setOrderNumber] = useState("");
  const [shippingMethods, setShippingMethods] = useState<ShippingMethod[]>([]);
  const [selectedShipping, setSelectedShipping] = useState<number | null>(null);
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [confirmRemove, setConfirmRemove] = useState<number | null>(null);

  useEffect(() => {
    api.shippingMethods.list().then((methods) => {
      setShippingMethods(methods);
      if (methods.length > 0) setSelectedShipping(methods[0].id);
    });
    api.taxRates.list().then(setTaxRates);
  }, []);

  const applyDiscount = async () => {
    try {
      const d = await api.discounts.lookup(discountCode);
      setDiscount({ type: d.discount_type, value: parseFloat(d.value) });
      setError("");
    } catch { setError("Invalid or expired discount code"); setDiscount(null); }
  };

  const subtotalAfterDiscount = discount
    ? discount.type === "percentage" ? total * (1 - discount.value / 100) : Math.max(0, total - discount.value)
    : total;

  const defaultTaxRate = taxRates.find((t) => t.is_default);
  const taxAmount = defaultTaxRate ? subtotalAfterDiscount * parseFloat(defaultTaxRate.rate) : 0;

  const selectedShippingMethod = shippingMethods.find((m) => m.id === selectedShipping);
  const shippingCost = selectedShippingMethod
    ? subtotalAfterDiscount >= parseFloat(selectedShippingMethod.min_order_amount)
      ? 0
      : parseFloat(selectedShippingMethod.price)
    : 0;

  const finalTotal = subtotalAfterDiscount + taxAmount + shippingCost;

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};
    if (!name.trim()) errors.name = "Name is required";
    const phoneErr = validatePhone(phone);
    if (phoneErr) errors.phone = phoneErr;
    if (!address.trim()) errors.address = "Address is required";
    if (!city.trim()) errors.city = "City is required";
    const zipErr = validateZip(zip);
    if (zipErr) errors.zip = zipErr;
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const canSubmit = name && phone && address && city && zip && items.length > 0 && !submitting;

  const placeOrder = async () => {
    if (!validateForm() || !canSubmit) return;
    setSubmitting(true);
    setError("");
    try {
      const order = await api.orders.create({
        source: "web", customer_name: name, customer_phone: phone,
        shipping_address: { address1: address, city, zip },
        line_items: items.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
        shipping_method_id: selectedShipping,
      });
      setOrderNumber(order.order_number);
      clearCart();
    } catch (e: any) { setError(e.message || "Failed to place order"); }
    finally { setSubmitting(false); }
  };

  const fieldInputStyle = (field: string) => ({
    ...baseStyles.input,
    borderColor: fieldErrors[field] ? colors.danger : undefined,
  });

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
                gap: spacing.sm, flexWrap: "wrap",
                padding: "12px 0", borderBottom: i < items.length - 1 ? `1px solid ${colors.border}` : undefined,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: spacing.sm }}>
                  {item.product.images.length > 0 ? (
                    <img src={item.product.images[0].src} alt={item.product.title} style={{ width: 48, height: 48, objectFit: "cover", borderRadius: radius.sm, flexShrink: 0 }} />
                  ) : (
                    <div style={{ width: 48, height: 48, background: colors.surfaceMuted, borderRadius: radius.sm, flexShrink: 0 }} />
                  )}
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.product.title}</div>
                    <div style={{ color: colors.textSecondary, fontSize: "13px" }}>{item.variant.title} &middot; ${item.variant.price}</div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <Button variant="secondary" size="sm" onClick={() => updateQuantity(item.variant.id, item.quantity - 1)}>-</Button>
                  <span style={{ width: 28, textAlign: "center", fontWeight: 600 }}>{item.quantity}</span>
                  <Button variant="secondary" size="sm" onClick={() => updateQuantity(item.variant.id, item.quantity + 1)}>+</Button>
                  <Button variant="danger" size="sm" onClick={() => setConfirmRemove(item.variant.id)}>Remove</Button>
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
          </div>

          {shippingMethods.length > 0 && (
            <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
              <h3 style={{ margin: "0 0 12px", fontSize: "16px" }}>Shipping Method</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {shippingMethods.map((method) => {
                  const isFree = subtotalAfterDiscount >= parseFloat(method.min_order_amount);
                  return (
                    <label key={method.id} style={{ display: "flex", alignItems: "flex-start", gap: "10px", cursor: "pointer" }}>
                      <input type="radio" name="shippingMethod" value={method.id} checked={selectedShipping === method.id}
                        onChange={() => setSelectedShipping(method.id)} style={{ marginTop: "2px" }} />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: "14px" }}>
                          {method.name} &mdash; {isFree ? <span style={{ color: colors.success }}>Free</span> : `$${parseFloat(method.price).toFixed(2)}`}
                        </div>
                        {parseFloat(method.min_order_amount) > 0 && (
                          <div style={{ color: colors.textSecondary, fontSize: "12px" }}>
                            Free on orders over ${parseFloat(method.min_order_amount).toFixed(2)}
                          </div>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: colors.textSecondary }}>Subtotal</span>
                <span>${subtotalAfterDiscount.toFixed(2)}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: colors.textSecondary }}>
                  Tax{defaultTaxRate ? ` (${(parseFloat(defaultTaxRate.rate) * 100).toFixed(0)}%)` : ""}
                </span>
                <span>${taxAmount.toFixed(2)}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: colors.textSecondary }}>Shipping</span>
                <span>{shippingCost === 0 ? <span style={{ color: colors.success }}>Free</span> : `$${shippingCost.toFixed(2)}`}</span>
              </div>
              <div style={{ borderTop: `1px solid ${colors.border}`, marginTop: "6px", paddingTop: "8px", display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 700, fontSize: "18px" }}>Total</span>
                <span style={{ fontWeight: 700, fontSize: "18px" }}>${finalTotal.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div style={baseStyles.card}>
            <h3 style={{ margin: "0 0 16px", fontSize: "16px" }}>Delivery Details</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div>
                <input placeholder="Full name *" value={name} onChange={(e) => { setName(e.target.value); setFieldErrors((p) => ({ ...p, name: "" })); }} style={fieldInputStyle("name")} />
                {fieldErrors.name && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.name}</div>}
              </div>
              <div>
                <input placeholder="Phone * (e.g. 010-1234-5678)" value={phone} onChange={(e) => { setPhone(e.target.value); setFieldErrors((p) => ({ ...p, phone: "" })); }} style={fieldInputStyle("phone")} />
                {fieldErrors.phone && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.phone}</div>}
              </div>
              <div>
                <input placeholder="Address *" value={address} onChange={(e) => { setAddress(e.target.value); setFieldErrors((p) => ({ ...p, address: "" })); }} style={fieldInputStyle("address")} />
                {fieldErrors.address && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.address}</div>}
              </div>
              <div style={{ display: "flex", gap: "10px" }}>
                <div style={{ flex: 1 }}>
                  <input placeholder="City *" value={city} onChange={(e) => { setCity(e.target.value); setFieldErrors((p) => ({ ...p, city: "" })); }} style={fieldInputStyle("city")} />
                  {fieldErrors.city && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.city}</div>}
                </div>
                <div style={{ width: 120 }}>
                  <input placeholder="ZIP *" value={zip} onChange={(e) => { setZip(e.target.value); setFieldErrors((p) => ({ ...p, zip: "" })); }} style={fieldInputStyle("zip")} />
                  {fieldErrors.zip && <div style={{ color: colors.danger, fontSize: "12px", marginTop: "4px" }}>{fieldErrors.zip}</div>}
                </div>
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

      {confirmRemove !== null && (
        <ConfirmDialog
          title="Remove item"
          message="Are you sure you want to remove this item from your cart?"
          confirmLabel="Remove"
          variant="danger"
          onConfirm={() => { removeItem(confirmRemove); setConfirmRemove(null); }}
          onCancel={() => setConfirmRemove(null)}
        />
      )}
    </div>
  );
}
