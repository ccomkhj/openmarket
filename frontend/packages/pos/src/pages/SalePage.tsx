import { useState, useRef, useEffect, useCallback } from "react";
import { api, useWebSocket, useToast, Button, ConfirmDialog, colors, baseStyles, spacing, radius, BarcodeScanner } from "@openmarket/shared";
import type { ProductVariant, CashPaymentResult, CardPaymentResult, Order } from "@openmarket/shared";
import { Receipt } from "../components/Receipt";
import type { ReceiptItem } from "../components/Receipt";
import { ReturnModal } from "../components/ReturnModal";
import { WeighedProductInput } from "../components/WeighedProductInput";
import { HealthDots } from "../components/HealthDots";
import { PaymentCashModal } from "../components/PaymentCashModal";
import { PaymentCardModal } from "../components/PaymentCardModal";

interface SaleItem {
  variant: ProductVariant;
  productTitle: string;
  quantity: number;
  quantityKg?: string;
}
interface ReceiptData { orderNumber: string; items: ReceiptItem[]; total: number; }

interface WeighedPrompt { variant: ProductVariant; productTitle: string; }

export function SalePage() {
  const [barcodeInput, setBarcodeInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [searchResults, setSearchResults] = useState<{ title: string; variants: ProductVariant[] }[]>([]);
  const [saleItems, setSaleItems] = useState<SaleItem[]>([]);
  const [error, setError] = useState("");
  const [receiptData, setReceiptData] = useState<ReceiptData | null>(null);
  const barcodeRef = useRef<HTMLInputElement>(null);
  const [showCameraScanner, setShowCameraScanner] = useState(false);
  const [showReturn, setShowReturn] = useState(false);
  const { toast } = useToast();
  const [confirmVoid, setConfirmVoid] = useState(false);
  const [weighedPrompt, setWeighedPrompt] = useState<WeighedPrompt | null>(null);
  const [payMethod, setPayMethod] = useState<"none" | "cash" | "card">("none");
  const [pendingOrder, setPendingOrder] = useState<Order | null>(null);
  const [pendingTotal, setPendingTotal] = useState<string>("0.00");
  const [lastTxId, setLastTxId] = useState<string | null>(null);
  const [lastSale, setLastSale] = useState<{ orderNumber: string; total: string; change: string; method: "cash" | "card" } | null>(null);
  const [confirmStorno, setConfirmStorno] = useState(false);

  useEffect(() => { barcodeRef.current?.focus(); }, []);

  const handleInventoryUpdate = useCallback(() => {}, []);
  useWebSocket(handleInventoryUpdate);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (weighedPrompt) { setWeighedPrompt(null); }
        else if (receiptData) { setReceiptData(null); barcodeRef.current?.focus(); }
        else if (error) { setError(""); }
        else if (showReturn) { setShowReturn(false); }
        return;
      }
      if (e.key === "F8" && saleItems.length > 0 && !receiptData && payMethod === "none") {
        e.preventDefault();
        handlePayCash();
        return;
      }
      if (e.key === "F4" && saleItems.length > 0) {
        e.preventDefault();
        setConfirmVoid(true);
        return;
      }
      if (e.key === "F9") {
        e.preventDefault();
        setShowReturn(true);
        return;
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [saleItems.length, receiptData, error, showReturn, weighedPrompt, payMethod]);

  const addByBarcode = async (barcode: string) => {
    setError("");
    try {
      const result = await api.variants.lookup(barcode);
      addToSale(result.title, {
        id: result.id, product_id: result.product_id, title: result.title,
        sku: result.sku ?? "", barcode: result.barcode ?? "", price: result.price,
        compare_at_price: null, position: 0,
        pricing_type: result.pricing_type,
        weight_unit: null,
        min_weight_kg: result.min_weight_kg,
        max_weight_kg: result.max_weight_kg,
        tare_kg: result.tare_kg,
      });
      setBarcodeInput("");
    } catch {
      setError(`No product found with barcode: ${barcode}`);
    }
  };

  const searchProducts = async (query: string) => {
    if (!query) { setSearchResults([]); return; }
    const products = await api.products.list({ status: "active", search: query });
    const full = await Promise.all(products.slice(0, 5).map((p) => api.products.get(p.id)));
    setSearchResults(full.map((p) => ({ title: p.title, variants: p.variants })));
  };

  const addToSale = (productTitle: string, variant: ProductVariant) => {
    if (lastSale) setLastSale(null);
    if (variant.pricing_type === "by_weight") {
      setWeighedPrompt({ variant, productTitle });
      setSearchResults([]);
      setSearchInput("");
      return;
    }
    setSaleItems((prev) => {
      const existing = prev.find((i) => i.variant.id === variant.id && !i.quantityKg);
      if (existing) return prev.map((i) => i.variant.id === variant.id && !i.quantityKg ? { ...i, quantity: i.quantity + 1 } : i);
      return [...prev, { variant, productTitle, quantity: 1 }];
    });
    setSearchResults([]); setSearchInput(""); barcodeRef.current?.focus();
  };

  const addWeighedToSale = (productTitle: string, variant: ProductVariant, quantityKg: number) => {
    if (lastSale) setLastSale(null);
    const qtyKgStr = quantityKg.toFixed(3);
    setSaleItems((prev) => [
      ...prev,
      { variant, productTitle, quantity: 1, quantityKg: qtyKgStr },
    ]);
    barcodeRef.current?.focus();
  };

  const updateQty = (variantId: number, qty: number) => {
    if (qty <= 0) { setSaleItems((prev) => prev.filter((i) => i.variant.id !== variantId || i.quantityKg)); return; }
    setSaleItems((prev) => prev.map((i) => i.variant.id === variantId && !i.quantityKg ? { ...i, quantity: qty } : i));
  };

  const removeItemAt = (index: number) => setSaleItems((prev) => prev.filter((_, idx) => idx !== index));
  const liveLineTotal = (item: SaleItem): number => {
    const price = parseFloat(item.variant.price);
    if (item.quantityKg != null) return parseFloat(item.quantityKg) * price;
    return (item.quantity ?? 1) * price;
  };
  const total = saleItems.reduce((sum, item) => sum + liveLineTotal(item), 0);

  const voidSale = () => setConfirmVoid(true);
  const doVoidSale = () => { setSaleItems([]); setConfirmVoid(false); toast("Sale voided"); barcodeRef.current?.focus(); };

  const buildReceiptItems = (order: Order): { receiptItems: ReceiptItem[]; receiptTotal: number; orderNumber: string } => {
    const serverLines = order.line_items ?? [];
    const receiptItems: ReceiptItem[] = saleItems.map((i, idx) => {
      const serverLine = serverLines[idx];
      return {
        productTitle: i.productTitle,
        variantTitle: i.quantityKg ? `${i.variant.title} (${i.quantityKg} kg)` : i.variant.title,
        quantity: i.quantity,
        price: i.variant.price,
        quantity_kg: i.quantityKg ?? null,
        line_total: serverLine?.line_total ?? null,
      };
    });
    const receiptTotal = saleItems.reduce((sum, i) => sum + liveLineTotal(i), 0);
    return { receiptItems, receiptTotal, orderNumber: order.order_number };
  };

  const createOrderForPayment = async (): Promise<Order | null> => {
    setError("");
    try {
      const order = await api.orders.create({
        source: "pos",
        line_items: saleItems.map((i) => {
          const line: Record<string, unknown> = { variant_id: i.variant.id, quantity: i.quantity };
          if (i.quantityKg) line.quantity_kg = i.quantityKg;
          return line;
        }),
      });
      return order;
    } catch (e: any) {
      setError(e.message);
      toast("Order creation failed", "error");
      return null;
    }
  };

  const handlePayCash = async () => {
    const order = await createOrderForPayment();
    if (!order) return;
    setPendingOrder(order);
    setPendingTotal(total.toFixed(2));
    setPayMethod("cash");
  };

  const handlePayCard = async () => {
    const order = await createOrderForPayment();
    if (!order) return;
    setPendingOrder(order);
    setPendingTotal(total.toFixed(2));
    setPayMethod("card");
  };

  const handlePaymentSuccess = (txId: string, order: Order) => {
    const { receiptItems, receiptTotal, orderNumber } = buildReceiptItems(order);
    setSaleItems([]);
    setPayMethod("none");
    setPendingOrder(null);
    setLastTxId(txId);
    setReceiptData({ orderNumber, items: receiptItems, total: receiptTotal });
    toast("Sale completed");
  };

  const handleCashPaid = (r: CashPaymentResult) => {
    if (pendingOrder) {
      setLastSale({
        orderNumber: pendingOrder.order_number,
        total: pendingTotal,
        change: r.change,
        method: "cash",
      });
      handlePaymentSuccess(r.transaction.id, pendingOrder);
    }
  };

  const handleCardPaid = (r: CardPaymentResult) => {
    if (pendingOrder) {
      setLastSale({
        orderNumber: pendingOrder.order_number,
        total: pendingTotal,
        change: "0.00",
        method: "card",
      });
      handlePaymentSuccess(r.transaction.id, pendingOrder);
    }
  };

  const doReprint = async () => {
    if (!lastTxId) return;
    try {
      const job = await api.receipts.reprint(lastTxId);
      if (job.status === "printed" || job.status === "queued") {
        toast("Receipt reprinted");
      } else {
        toast(`Reprint status: ${job.status}${job.last_error ? ` — ${job.last_error}` : ""}`, "error");
      }
    } catch (e: any) {
      toast(`Reprint failed: ${e.message}`, "error");
    }
  };

  const doStorno = async () => {
    if (!lastTxId) return;
    try {
      await api.storno.void(lastTxId);
      setLastTxId(null);
      setLastSale(null);
      setConfirmStorno(false);
      toast("Transaction voided (Storno)");
    } catch (e: any) {
      toast(`Storno failed: ${e.message}`, "error");
      setConfirmStorno(false);
    }
  };

  const handleBarcodeKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter" && barcodeInput.trim()) addByBarcode(barcodeInput.trim()); };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Left: Input Area */}
      <div style={{ flex: 1, padding: spacing.lg, borderRight: `1px solid ${colors.border}`, background: colors.surface, display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
          <h2 style={{ margin: 0, color: colors.brand }}>POS</h2>
          <div style={{ display: "flex", alignItems: "center", gap: spacing.sm }}>
            <HealthDots />
            <Button variant="secondary" size="sm" onClick={() => setShowReturn(true)}>Returns (F9)</Button>
          </div>
        </div>

        <div style={{ marginBottom: spacing.lg }}>
          <label style={{ display: "block", fontWeight: 600, marginBottom: "4px", fontSize: "13px", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: "0.5px" }}>Scan Barcode</label>
          <input ref={barcodeRef} value={barcodeInput} onChange={(e) => setBarcodeInput(e.target.value)} onKeyDown={handleBarcodeKeyDown}
            placeholder="Scan or type barcode..." style={{ ...baseStyles.input, padding: "12px", fontSize: "16px" }} />
          <Button variant="secondary" size="sm" onClick={() => setShowCameraScanner(true)} style={{ flexShrink: 0, marginTop: "8px" }}>📷 Camera Scan</Button>
        </div>

        <div style={{ marginBottom: spacing.lg }}>
          <label style={{ display: "block", fontWeight: 600, marginBottom: "4px", fontSize: "13px", color: colors.textSecondary, textTransform: "uppercase", letterSpacing: "0.5px" }}>Search Product</label>
          <input value={searchInput} onChange={(e) => { setSearchInput(e.target.value); searchProducts(e.target.value); }}
            placeholder="Type to search..." style={baseStyles.input} />
          {searchResults.length > 0 && (
            <div style={{ border: `1px solid ${colors.border}`, borderRadius: radius.sm, maxHeight: 200, overflowY: "auto", marginTop: "4px", background: colors.surface }}>
              {searchResults.map((p) => p.variants.map((v) => (
                <div key={v.id} onClick={() => addToSale(p.title, v)}
                  style={{ padding: "10px 12px", cursor: "pointer", borderBottom: `1px solid ${colors.border}`, fontSize: "14px" }}>
                  <strong>{p.title}</strong> — {v.title} <span style={{ color: colors.brand, fontWeight: 600 }}>${v.price}</span>
                </div>
              )))}
            </div>
          )}
        </div>

        {error && <div style={{ background: colors.dangerSurface, color: colors.danger, padding: "10px 14px", borderRadius: radius.sm, fontSize: "14px", marginBottom: spacing.md }}>{error}</div>}
      </div>

      {/* Right: Current Sale */}
      <div style={{ width: 420, padding: spacing.lg, display: "flex", flexDirection: "column", background: colors.surfaceMuted }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
          <h3 style={{ margin: 0 }}>Current Sale</h3>
          {saleItems.length > 0 && <Button variant="danger" size="sm" onClick={voidSale}>Void (F4)</Button>}
        </div>

        <div style={{ flex: 1, overflowY: "auto" }}>
          {saleItems.length === 0 ? (
            <div style={{ textAlign: "center", padding: spacing.xl, color: colors.textDisabled }}>No items scanned</div>
          ) : saleItems.map((item, idx) => (
            <div key={`${item.variant.id}-${idx}`} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "10px 12px", marginBottom: "6px",
              background: colors.surface, borderRadius: radius.sm, border: `1px solid ${colors.border}`,
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.productTitle}</div>
                <div style={{ color: colors.textSecondary, fontSize: "13px" }}>
                  {item.variant.title} &middot; {item.quantityKg ? `${item.quantityKg} kg @ $${item.variant.price}/kg = $${liveLineTotal(item).toFixed(2)}` : `$${item.variant.price}`}
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                {item.quantityKg ? (
                  <span style={{ fontWeight: 600, fontSize: "14px", padding: "4px 8px" }}>
                    {item.quantityKg} kg
                  </span>
                ) : (
                  <>
                    <Button variant="secondary" size="sm" onClick={() => updateQty(item.variant.id, item.quantity - 1)}>-</Button>
                    <input
                      value={item.quantity}
                      onChange={(e) => { const v = parseInt(e.target.value); if (!isNaN(v)) updateQty(item.variant.id, v); }}
                      style={{ width: 40, textAlign: "center", padding: "4px", border: `1px solid ${colors.borderStrong}`, borderRadius: radius.sm, fontSize: "14px", fontWeight: 600 }}
                    />
                    <Button variant="secondary" size="sm" onClick={() => updateQty(item.variant.id, item.quantity + 1)}>+</Button>
                  </>
                )}
                <Button variant="ghost" size="sm" onClick={() => removeItemAt(idx)} style={{ color: colors.danger }}>&#10005;</Button>
              </div>
            </div>
          ))}
        </div>

        <div style={{ borderTop: `2px solid ${colors.textPrimary}`, paddingTop: spacing.md }}>
          <p style={{ fontSize: "28px", fontWeight: 700, textAlign: "right", margin: `0 0 ${spacing.md}` }}>${total.toFixed(2)}</p>
          <div style={{ display: "flex", gap: spacing.sm, marginBottom: spacing.sm }}>
            <Button variant="primary" size="lg" fullWidth disabled={saleItems.length === 0 || payMethod !== "none"} onClick={handlePayCash}
              style={{ background: "#1A7F37", padding: "14px", fontSize: "16px" }}>
              Pay Cash (F8)
            </Button>
            <Button variant="primary" size="lg" fullWidth disabled={saleItems.length === 0 || payMethod !== "none"} onClick={handlePayCard}
              style={{ background: "#0070f3", padding: "14px", fontSize: "16px" }}>
              Pay Card
            </Button>
          </div>
          {lastSale && (
            <div style={{
              marginTop: spacing.sm,
              padding: spacing.md,
              background: "#E6F4EA",
              border: "1px solid #34A853",
              borderRadius: radius.sm,
              fontSize: 14,
            }}>
              <div style={{ fontWeight: 700, color: "#1A7F37", marginBottom: 4 }}>
                ✓ Paid — Order #{lastSale.orderNumber}
              </div>
              <div style={{ color: colors.textPrimary }}>
                Total EUR {lastSale.total}
                {lastSale.method === "cash" && parseFloat(lastSale.change) > 0 && (
                  <> · <strong>Change EUR {lastSale.change}</strong></>
                )}
                {lastSale.method === "card" && <> · card</>}
              </div>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginTop: 4 }}>
                Scan next item to start a new sale
              </div>
            </div>
          )}
          {lastTxId && (
            <div style={{ display: "flex", gap: spacing.xs, marginTop: spacing.xs }}>
              <Button variant="secondary" size="sm" fullWidth onClick={doReprint}>
                Reprint receipt
              </Button>
              <Button variant="danger" size="sm" fullWidth onClick={() => setConfirmStorno(true)}>
                Storno last sale
              </Button>
            </div>
          )}
        </div>
      </div>
      {showCameraScanner && (
        <BarcodeScanner
          onDetected={(code) => { setShowCameraScanner(false); addByBarcode(code); }}
          onClose={() => setShowCameraScanner(false)}
        />
      )}
      {receiptData && (
        <Receipt
          orderNumber={receiptData.orderNumber}
          items={receiptData.items}
          total={receiptData.total}
          onClose={() => { setReceiptData(null); barcodeRef.current?.focus(); }}
        />
      )}
      {showReturn && <ReturnModal onClose={() => setShowReturn(false)} />}
      {confirmVoid && (
        <ConfirmDialog
          title="Void Sale"
          message="All items will be cleared from the current sale. This cannot be undone."
          confirmLabel="Void Sale"
          variant="danger"
          onConfirm={doVoidSale}
          onCancel={() => setConfirmVoid(false)}
        />
      )}
      {weighedPrompt && (
        <WeighedProductInput
          title={`${weighedPrompt.productTitle} - ${weighedPrompt.variant.title}`}
          pricePerKg={weighedPrompt.variant.price}
          weightUnit={weighedPrompt.variant.weight_unit ?? null}
          minKg={weighedPrompt.variant.min_weight_kg ?? null}
          maxKg={weighedPrompt.variant.max_weight_kg ?? null}
          onConfirm={(kg) => {
            addWeighedToSale(weighedPrompt.productTitle, weighedPrompt.variant, kg);
            setWeighedPrompt(null);
          }}
          onCancel={() => setWeighedPrompt(null)}
        />
      )}
      {payMethod === "cash" && pendingOrder !== null && (
        <PaymentCashModal
          orderId={pendingOrder.id}
          total={pendingTotal}
          onPaid={handleCashPaid}
          onCancel={() => { setPayMethod("none"); setPendingOrder(null); }}
        />
      )}
      {payMethod === "card" && pendingOrder !== null && (
        <PaymentCardModal
          orderId={pendingOrder.id}
          total={pendingTotal}
          onPaid={handleCardPaid}
          onCancel={() => { setPayMethod("none"); setPendingOrder(null); }}
        />
      )}
      {confirmStorno && (
        <ConfirmDialog
          title="Storno last sale"
          message="This will void the last completed transaction via TSE. The receipt will be cancelled. This cannot be undone."
          confirmLabel="Void transaction"
          variant="danger"
          onConfirm={doStorno}
          onCancel={() => setConfirmStorno(false)}
        />
      )}
    </div>
  );
}
