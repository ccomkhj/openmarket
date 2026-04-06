import { useState, useRef, useEffect, useCallback } from "react";
import { api, useWebSocket, useToast, Button, ConfirmDialog, colors, baseStyles, spacing, radius, BarcodeScanner } from "@openmarket/shared";
import type { ProductVariant } from "@openmarket/shared";
import { Receipt } from "../components/Receipt";
import type { ReceiptItem } from "../components/Receipt";
import { ReturnModal } from "../components/ReturnModal";

interface SaleItem { variant: ProductVariant; productTitle: string; quantity: number; }
interface ReceiptData { orderNumber: string; items: ReceiptItem[]; total: number; }

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

  useEffect(() => { barcodeRef.current?.focus(); }, []);

  const handleInventoryUpdate = useCallback(() => {}, []);
  useWebSocket(handleInventoryUpdate);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (receiptData) { setReceiptData(null); barcodeRef.current?.focus(); }
        else if (error) { setError(""); }
        else if (showReturn) { setShowReturn(false); }
        return;
      }
      if (e.key === "F8" && saleItems.length > 0 && !receiptData) {
        e.preventDefault();
        completeSale();
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
  }, [saleItems.length, receiptData, error, showReturn]);

  const addByBarcode = async (barcode: string) => {
    setError("");
    try {
      const result = await api.variants.lookup(barcode);
      addToSale(result.product_title, {
        id: result.id, product_id: result.product_id, title: result.title,
        sku: result.sku, barcode: result.barcode, price: result.price,
        compare_at_price: result.compare_at_price, position: 0,
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
    setSaleItems((prev) => {
      const existing = prev.find((i) => i.variant.id === variant.id);
      if (existing) return prev.map((i) => i.variant.id === variant.id ? { ...i, quantity: i.quantity + 1 } : i);
      return [...prev, { variant, productTitle, quantity: 1 }];
    });
    setSearchResults([]); setSearchInput(""); barcodeRef.current?.focus();
  };

  const updateQty = (variantId: number, qty: number) => {
    if (qty <= 0) { setSaleItems((prev) => prev.filter((i) => i.variant.id !== variantId)); return; }
    setSaleItems((prev) => prev.map((i) => i.variant.id === variantId ? { ...i, quantity: qty } : i));
  };

  const removeItem = (variantId: number) => setSaleItems((prev) => prev.filter((i) => i.variant.id !== variantId));
  const total = saleItems.reduce((sum, item) => sum + parseFloat(item.variant.price) * item.quantity, 0);

  const voidSale = () => setConfirmVoid(true);
  const doVoidSale = () => { setSaleItems([]); setConfirmVoid(false); toast("Sale voided"); barcodeRef.current?.focus(); };

  const completeSale = async () => {
    setError("");
    try {
      const order = await api.orders.create({ source: "pos", line_items: saleItems.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })) });
      const receiptItems: ReceiptItem[] = saleItems.map((i) => ({
        productTitle: i.productTitle,
        variantTitle: i.variant.title,
        quantity: i.quantity,
        price: i.variant.price,
      }));
      const receiptTotal = saleItems.reduce((sum, i) => sum + parseFloat(i.variant.price) * i.quantity, 0);
      setSaleItems([]);
      setReceiptData({ orderNumber: String(order.order_number), items: receiptItems, total: receiptTotal });
      toast("Sale completed");
    } catch (e: any) { setError(e.message); toast("Sale failed", "error"); }
  };

  const handleBarcodeKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter" && barcodeInput.trim()) addByBarcode(barcodeInput.trim()); };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Left: Input Area */}
      <div style={{ flex: 1, padding: spacing.lg, borderRight: `1px solid ${colors.border}`, background: colors.surface, display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
          <h2 style={{ margin: 0, color: colors.brand }}>POS</h2>
          <Button variant="secondary" size="sm" onClick={() => setShowReturn(true)}>Returns (F9)</Button>
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
          ) : saleItems.map((item) => (
            <div key={item.variant.id} style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "10px 12px", marginBottom: "6px",
              background: colors.surface, borderRadius: radius.sm, border: `1px solid ${colors.border}`,
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "14px" }}>{item.productTitle}</div>
                <div style={{ color: colors.textSecondary, fontSize: "13px" }}>{item.variant.title} &middot; ${item.variant.price}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Button variant="secondary" size="sm" onClick={() => updateQty(item.variant.id, item.quantity - 1)}>-</Button>
                <input
                  value={item.quantity}
                  onChange={(e) => { const v = parseInt(e.target.value); if (!isNaN(v)) updateQty(item.variant.id, v); }}
                  style={{ width: 40, textAlign: "center", padding: "4px", border: `1px solid ${colors.borderStrong}`, borderRadius: radius.sm, fontSize: "14px", fontWeight: 600 }}
                />
                <Button variant="secondary" size="sm" onClick={() => updateQty(item.variant.id, item.quantity + 1)}>+</Button>
                <Button variant="ghost" size="sm" onClick={() => removeItem(item.variant.id)} style={{ color: colors.danger }}>&#10005;</Button>
              </div>
            </div>
          ))}
        </div>

        <div style={{ borderTop: `2px solid ${colors.textPrimary}`, paddingTop: spacing.md }}>
          <p style={{ fontSize: "28px", fontWeight: 700, textAlign: "right", margin: `0 0 ${spacing.md}` }}>${total.toFixed(2)}</p>
          <Button variant="primary" size="lg" fullWidth disabled={saleItems.length === 0} onClick={completeSale}
            style={{ background: "#1A7F37", padding: "14px", fontSize: "18px" }}>
            Complete Sale (F8)
          </Button>
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
    </div>
  );
}
