import { useState } from "react";
import { api, type VariantDetail } from "@openmarket/shared";

export function VariantEditModal({
  initial, onSaved, onCancel,
}: {
  initial: VariantDetail;
  onSaved: (v: VariantDetail) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial.title);
  const [sku, setSku] = useState(initial.sku ?? "");
  const [barcode, setBarcode] = useState(initial.barcode ?? "");
  const [price, setPrice] = useState(initial.price);
  const [vatRate, setVatRate] = useState(initial.vat_rate);
  const [pricingType, setPricingType] = useState(initial.pricing_type);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const updated = await api.variants.update(initial.id, {
        title,
        sku: sku || null,
        barcode: barcode || null,
        price,
        vat_rate: vatRate,
        pricing_type: pricingType,
      });
      onSaved(updated);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <form onSubmit={submit} style={{ background: "white", padding: 24, minWidth: 400 }}>
        <h2>Edit variant</h2>
        <div><label>Title: <input value={title} onChange={(e) => setTitle(e.target.value)} required /></label></div>
        <div><label>SKU: <input value={sku} onChange={(e) => setSku(e.target.value)} /></label></div>
        <div><label>Barcode: <input value={barcode} onChange={(e) => setBarcode(e.target.value)} /></label></div>
        <div><label>Price (gross, EUR): <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} required /></label></div>
        <div>
          <label>VAT %:
            <select value={vatRate} onChange={(e) => setVatRate(e.target.value)}>
              <option value="7.00">7%</option>
              <option value="19.00">19%</option>
              <option value="0.00">0%</option>
              <option value="10.70">10.7%</option>
              <option value="5.50">5.5%</option>
            </select>
          </label>
        </div>
        <div>
          <label>Pricing:
            <select value={pricingType} onChange={(e) => setPricingType(e.target.value as "fixed" | "by_weight")}>
              <option value="fixed">Fixed</option>
              <option value="by_weight">By weight</option>
            </select>
          </label>
        </div>
        {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
        <div style={{ marginTop: 12 }}>
          <button type="submit" disabled={busy}>{busy ? "Saving..." : "Save"}</button>
          <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
        </div>
      </form>
    </div>
  );
}
