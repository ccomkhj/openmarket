import { useEffect, useState } from "react";
import { api, Button, Spinner, useToast, colors, baseStyles, spacing } from "@openmarket/shared";
import type { TaxRate, ShippingMethod, Discount, Location } from "@openmarket/shared";

export function SettingsPage() {
  const { toast } = useToast();
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [shippingMethods, setShippingMethods] = useState<ShippingMethod[]>([]);
  const [discounts, setDiscounts] = useState<Discount[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);

  const [taxName, setTaxName] = useState("");
  const [taxRate, setTaxRate] = useState("");
  const [taxRegion, setTaxRegion] = useState("");
  const [taxDefault, setTaxDefault] = useState(false);

  const [shipName, setShipName] = useState("");
  const [shipPrice, setShipPrice] = useState("");
  const [shipMinOrder, setShipMinOrder] = useState("");

  const [discCode, setDiscCode] = useState("");
  const [discType, setDiscType] = useState("percentage");
  const [discValue, setDiscValue] = useState("");
  const [discStart, setDiscStart] = useState("");
  const [discEnd, setDiscEnd] = useState("");

  const loadAll = async () => {
    setLoading(true);
    const [t, s, d, l] = await Promise.all([
      api.taxRates.list(), api.shippingMethods.list(), api.discounts.list(), api.locations.list(),
    ]);
    setTaxRates(t); setShippingMethods(s); setDiscounts(d); setLocations(l);
    setLoading(false);
  };

  useEffect(() => { loadAll(); }, []);

  const createTax = async () => {
    if (!taxName || !taxRate) return;
    await api.taxRates.create({ name: taxName, rate: taxRate, region: taxRegion, is_default: taxDefault });
    setTaxName(""); setTaxRate(""); setTaxRegion(""); setTaxDefault(false);
    toast("Tax rate created");
    loadAll();
  };

  const createShipping = async () => {
    if (!shipName || !shipPrice) return;
    await api.shippingMethods.create({ name: shipName, price: shipPrice, min_order_amount: shipMinOrder || "0", is_active: true });
    setShipName(""); setShipPrice(""); setShipMinOrder("");
    toast("Shipping method created");
    loadAll();
  };

  const createDiscount = async () => {
    if (!discCode || !discValue || !discStart || !discEnd) return;
    await api.discounts.create({
      code: discCode, discount_type: discType, value: discValue,
      starts_at: new Date(discStart).toISOString(), ends_at: new Date(discEnd).toISOString(),
    });
    setDiscCode(""); setDiscValue(""); setDiscStart(""); setDiscEnd("");
    toast("Discount created");
    loadAll();
  };

  const deleteDiscount = async (id: number) => {
    await api.discounts.delete(id);
    toast("Discount deleted");
    loadAll();
  };

  const sectionTitle: React.CSSProperties = { margin: `0 0 ${spacing.md}`, fontSize: "16px" };
  const formRow: React.CSSProperties = { display: "flex", gap: spacing.sm, marginBottom: spacing.sm };

  if (loading) return <div style={baseStyles.container}><Spinner label="Loading settings..." /></div>;

  return (
    <div style={baseStyles.container}>
      <h2 style={{ marginBottom: spacing.lg }}>Settings</h2>

      {/* Locations */}
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <h3 style={sectionTitle}>Locations</h3>
        {locations.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: "14px" }}>No locations configured</div>
        ) : locations.map((l) => (
          <div key={l.id} style={{ fontSize: "14px", padding: "4px 0" }}>
            <strong>{l.name}</strong> {l.address && <span style={{ color: colors.textSecondary }}>&mdash; {l.address}</span>}
          </div>
        ))}
      </div>

      {/* Tax Rates */}
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <h3 style={sectionTitle}>Tax Rates</h3>
        {taxRates.map((t) => (
          <div key={t.id} style={{ fontSize: "14px", padding: "4px 0", display: "flex", justifyContent: "space-between" }}>
            <span><strong>{t.name}</strong> &mdash; {(parseFloat(t.rate) * 100).toFixed(1)}% {t.region && `(${t.region})`}</span>
            {t.is_default && <span style={{ color: colors.brand, fontSize: "12px", fontWeight: 600 }}>DEFAULT</span>}
          </div>
        ))}
        <div style={{ ...formRow, marginTop: spacing.md }}>
          <input placeholder="Name *" value={taxName} onChange={(e) => setTaxName(e.target.value)} style={{ ...baseStyles.input, flex: 1 }} />
          <input placeholder="Rate (e.g. 0.10)" value={taxRate} onChange={(e) => setTaxRate(e.target.value)} style={{ ...baseStyles.input, width: 120 }} />
          <input placeholder="Region" value={taxRegion} onChange={(e) => setTaxRegion(e.target.value)} style={{ ...baseStyles.input, width: 100 }} />
          <label style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "13px", whiteSpace: "nowrap" }}>
            <input type="checkbox" checked={taxDefault} onChange={(e) => setTaxDefault(e.target.checked)} /> Default
          </label>
          <Button variant="primary" size="sm" onClick={createTax}>Add</Button>
        </div>
      </div>

      {/* Shipping Methods */}
      <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
        <h3 style={sectionTitle}>Shipping Methods</h3>
        {shippingMethods.map((s) => (
          <div key={s.id} style={{ fontSize: "14px", padding: "4px 0" }}>
            <strong>{s.name}</strong> &mdash; ${s.price} {parseFloat(s.min_order_amount) > 0 && `(free over $${s.min_order_amount})`}
          </div>
        ))}
        <div style={{ ...formRow, marginTop: spacing.md }}>
          <input placeholder="Name *" value={shipName} onChange={(e) => setShipName(e.target.value)} style={{ ...baseStyles.input, flex: 1 }} />
          <input placeholder="Price *" value={shipPrice} onChange={(e) => setShipPrice(e.target.value)} style={{ ...baseStyles.input, width: 100 }} />
          <input placeholder="Free above $" value={shipMinOrder} onChange={(e) => setShipMinOrder(e.target.value)} style={{ ...baseStyles.input, width: 120 }} />
          <Button variant="primary" size="sm" onClick={createShipping}>Add</Button>
        </div>
      </div>

      {/* Discounts */}
      <div style={baseStyles.card}>
        <h3 style={sectionTitle}>Discount Codes</h3>
        {discounts.length === 0 ? (
          <div style={{ color: colors.textSecondary, fontSize: "14px", marginBottom: spacing.md }}>No discounts configured</div>
        ) : (
          <div style={{ marginBottom: spacing.md }}>
            {discounts.map((d) => (
              <div key={d.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: `1px solid ${colors.border}`, fontSize: "14px" }}>
                <div>
                  <strong>{d.code}</strong> &mdash; {d.discount_type === "percentage" ? `${d.value}%` : `$${d.value}`} off
                  <span style={{ color: colors.textSecondary, fontSize: "12px", marginLeft: spacing.sm }}>
                    {new Date(d.starts_at).toLocaleDateString()} - {new Date(d.ends_at).toLocaleDateString()}
                  </span>
                </div>
                <Button variant="danger" size="sm" onClick={() => deleteDiscount(d.id)}>Delete</Button>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: spacing.sm }}>
          <div style={formRow}>
            <input placeholder="Code *" value={discCode} onChange={(e) => setDiscCode(e.target.value)} style={{ ...baseStyles.input, flex: 1 }} />
            <select value={discType} onChange={(e) => setDiscType(e.target.value)} style={{ ...baseStyles.input, width: 130 }}>
              <option value="percentage">Percentage</option>
              <option value="fixed">Fixed Amount</option>
            </select>
            <input placeholder="Value *" value={discValue} onChange={(e) => setDiscValue(e.target.value)} style={{ ...baseStyles.input, width: 100 }} />
          </div>
          <div style={formRow}>
            <label style={{ fontSize: "13px", color: colors.textSecondary, display: "flex", alignItems: "center", gap: "4px" }}>
              Start: <input type="date" value={discStart} onChange={(e) => setDiscStart(e.target.value)} style={{ ...baseStyles.input, width: "auto" }} />
            </label>
            <label style={{ fontSize: "13px", color: colors.textSecondary, display: "flex", alignItems: "center", gap: "4px" }}>
              End: <input type="date" value={discEnd} onChange={(e) => setDiscEnd(e.target.value)} style={{ ...baseStyles.input, width: "auto" }} />
            </label>
            <Button variant="primary" size="sm" onClick={createDiscount}>Add Discount</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
