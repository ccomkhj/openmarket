import { useState, useRef, useEffect, useCallback } from "react";
import { api, useWebSocket } from "@openmarket/shared";
import type { Product, ProductVariant } from "@openmarket/shared";

interface SaleItem { variant: ProductVariant; productTitle: string; quantity: number; }

export function SalePage() {
  const [barcodeInput, setBarcodeInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [saleItems, setSaleItems] = useState<SaleItem[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const barcodeRef = useRef<HTMLInputElement>(null);

  useEffect(() => { barcodeRef.current?.focus(); }, []);
  useEffect(() => {
    if (success) { const timer = setTimeout(() => { setSuccess(""); barcodeRef.current?.focus(); }, 3000); return () => clearTimeout(timer); }
  }, [success]);

  const handleInventoryUpdate = useCallback(() => {}, []);
  useWebSocket(handleInventoryUpdate);

  const addByBarcode = async (barcode: string) => {
    setError("");
    try {
      const products = await api.products.list({ status: "active" });
      for (const p of products) {
        const full = await api.products.get(p.id);
        const variant = full.variants.find((v) => v.barcode === barcode);
        if (variant) { addToSale(full.title, variant); setBarcodeInput(""); return; }
      }
      setError(`No product found with barcode: ${barcode}`);
    } catch { setError("Scan failed"); }
  };

  const searchProducts = async (query: string) => {
    if (!query) { setSearchResults([]); return; }
    const products = await api.products.list({ status: "active", search: query });
    const full = await Promise.all(products.slice(0, 5).map((p) => api.products.get(p.id)));
    setSearchResults(full);
  };

  const addToSale = (productTitle: string, variant: ProductVariant) => {
    setSaleItems((prev) => {
      const existing = prev.find((i) => i.variant.id === variant.id);
      if (existing) { return prev.map((i) => i.variant.id === variant.id ? { ...i, quantity: i.quantity + 1 } : i); }
      return [...prev, { variant, productTitle, quantity: 1 }];
    });
    setSearchResults([]); setSearchInput(""); barcodeRef.current?.focus();
  };

  const removeItem = (variantId: number) => { setSaleItems((prev) => prev.filter((i) => i.variant.id !== variantId)); };

  const total = saleItems.reduce((sum, item) => sum + parseFloat(item.variant.price) * item.quantity, 0);

  const completeSale = async () => {
    setError("");
    try {
      await api.orders.create({ source: "pos", line_items: saleItems.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })) });
      setSaleItems([]); setSuccess("Sale completed!");
    } catch (e: any) { setError(e.message); }
  };

  const handleBarcodeKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter" && barcodeInput.trim()) { addByBarcode(barcodeInput.trim()); } };

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      <div style={{ flex: 1, padding: "1rem", borderRight: "1px solid #ddd" }}>
        <h2>POS</h2>
        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", fontWeight: "bold", marginBottom: "0.25rem" }}>Scan Barcode</label>
          <input ref={barcodeRef} value={barcodeInput} onChange={(e) => setBarcodeInput(e.target.value)} onKeyDown={handleBarcodeKeyDown}
            placeholder="Scan or type barcode..." style={{ width: "100%", padding: "0.75rem", fontSize: "1.1rem", boxSizing: "border-box" }} />
        </div>
        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", fontWeight: "bold", marginBottom: "0.25rem" }}>Search Product</label>
          <input value={searchInput} onChange={(e) => { setSearchInput(e.target.value); searchProducts(e.target.value); }}
            placeholder="Type to search..." style={{ width: "100%", padding: "0.5rem", boxSizing: "border-box" }} />
          {searchResults.length > 0 && (
            <div style={{ border: "1px solid #ddd", maxHeight: 200, overflowY: "auto" }}>
              {searchResults.map((p) => p.variants.map((v) => (
                <div key={v.id} onClick={() => addToSale(p.title, v)}
                  style={{ padding: "0.5rem", cursor: "pointer", borderBottom: "1px solid #eee" }}>
                  {p.title} - {v.title} (${v.price})
                </div>
              )))}
            </div>
          )}
        </div>
        {error && <p style={{ color: "red", fontWeight: "bold" }}>{error}</p>}
        {success && <p style={{ color: "green", fontWeight: "bold", fontSize: "1.2rem" }}>{success}</p>}
      </div>
      <div style={{ width: 400, padding: "1rem", display: "flex", flexDirection: "column" }}>
        <h3>Current Sale</h3>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {saleItems.length === 0 ? <p style={{ color: "#999" }}>No items scanned</p> : saleItems.map((item) => (
            <div key={item.variant.id} style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: "1px solid #eee" }}>
              <div><strong>{item.productTitle}</strong> - {item.variant.title}<br />${item.variant.price} x {item.quantity}</div>
              <button onClick={() => removeItem(item.variant.id)} style={{ alignSelf: "center" }}>X</button>
            </div>
          ))}
        </div>
        <div style={{ borderTop: "2px solid #333", paddingTop: "1rem" }}>
          <p style={{ fontSize: "1.5rem", fontWeight: "bold" }}>Total: ${total.toFixed(2)}</p>
          <button onClick={completeSale} disabled={saleItems.length === 0}
            style={{ width: "100%", padding: "1rem", fontSize: "1.2rem", background: "#4CAF50", color: "white", border: "none", cursor: "pointer" }}>
            Complete Sale
          </button>
        </div>
      </div>
    </div>
  );
}
