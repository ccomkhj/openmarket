import { useEffect, useState, useCallback, Fragment } from "react";
import { VariantEditModal } from "./VariantEdit";
import { api, useWebSocket, useToast, useDebounce, Button, Spinner, ConfirmDialog, CameraCapture, colors, baseStyles, spacing, radius, BarcodeScanner, OCRScanner } from "@openmarket/shared";
import type { Product, ProductListWithPrice, ProductVariant, InventoryLevel, Location, VariantDetail } from "@openmarket/shared";

type PricingType = "fixed" | "by_weight";
type WeightUnit = "kg" | "g" | "100g";

interface VariantDraft {
  pricing_type: PricingType;
  weight_unit: WeightUnit;
  min_weight_kg: string;
  max_weight_kg: string;
  tare_kg: string;
  price: string;
  sku: string;
  barcode: string;
  title: string;
  compare_at_price: string;
}

const makeDraftFromVariant = (v: ProductVariant): VariantDraft => ({
  pricing_type: (v.pricing_type === "by_weight" ? "by_weight" : "fixed") as PricingType,
  weight_unit: (v.weight_unit ?? "kg") as WeightUnit,
  min_weight_kg: v.min_weight_kg ?? "",
  max_weight_kg: v.max_weight_kg ?? "",
  tare_kg: v.tare_kg ?? "",
  price: v.price ?? "",
  sku: v.sku ?? "",
  barcode: v.barcode ?? "",
  title: v.title ?? "",
  compare_at_price: v.compare_at_price ?? "",
});

export function ProductsInventoryPage() {
  const [products, setProducts] = useState<ProductListWithPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [inventory, setInventory] = useState<Record<number, InventoryLevel>>({});
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedProduct, setExpandedProduct] = useState<Product | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newHandle, setNewHandle] = useState("");
  const [newType, setNewType] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [newBarcode, setNewBarcode] = useState("");
  const [newPricingType, setNewPricingType] = useState<PricingType>("fixed");
  const [newWeightUnit, setNewWeightUnit] = useState<WeightUnit>("kg");
  const [newMinWeight, setNewMinWeight] = useState("");
  const [newMaxWeight, setNewMaxWeight] = useState("");
  const [newTareWeight, setNewTareWeight] = useState("");
  const [editingVariantId, setEditingVariantId] = useState<number | null>(null);
  const [variantDraft, setVariantDraft] = useState<VariantDraft | null>(null);
  const [stockInputs, setStockInputs] = useState<Record<number, string>>({});
  const [showBarcodeScanner, setShowBarcodeScanner] = useState(false);
  const [showOCRScanner, setShowOCRScanner] = useState(false);
  const [showCamera, setShowCamera] = useState(false);
  const [capturedImage, setCapturedImage] = useState<{ blob: Blob; preview: string } | null>(null);
  const [variantForModal, setVariantForModal] = useState<VariantDetail | null>(null);
  const { toast } = useToast();
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedLocationId, setSelectedLocationId] = useState<number>(1);
  const debouncedSearch = useDebounce(search, 300);

  const loadProducts = async () => {
    setLoading(true);
    const prods = await api.products.list({ search: search || undefined });
    setProducts(prods);
    setLoading(false);
  };

  const loadInventory = async () => {
    const levels = await api.inventory.levels(selectedLocationId);
    const map: Record<number, InventoryLevel> = {};
    for (const l of levels) map[l.inventory_item_id] = l;
    setInventory(map);
  };

  useEffect(() => {
    loadProducts();
    loadInventory();
    api.locations.list().then((locs) => {
      setLocations(locs);
      if (locs.length > 0) setSelectedLocationId(locs[0].id);
    });
  }, [debouncedSearch]);

  useEffect(() => { loadInventory(); }, [selectedLocationId]);

  const handleInventoryUpdate = useCallback((update: { inventory_item_id: number; available: number; location_id: number }) => {
    setInventory((prev) => ({
      ...prev,
      [update.inventory_item_id]: { ...prev[update.inventory_item_id], available: update.available },
    }));
  }, []);
  useWebSocket(handleInventoryUpdate);

  const expand = async (id: number) => {
    if (expandedId === id) { setExpandedId(null); setExpandedProduct(null); return; }
    setExpandedId(id);
    setExpandedProduct(await api.products.get(id));
  };

  const adjustStock = async (inventoryItemId: number, delta: number) => {
    try {
      await api.inventory.adjust({ inventory_item_id: inventoryItemId, location_id: selectedLocationId, available_adjustment: delta });
      await loadInventory();
      toast(`Stock adjusted by ${delta > 0 ? "+" : ""}${delta}`);
    } catch { toast("Failed to adjust stock", "error"); }
  };

  const setStock = async (inventoryItemId: number) => {
    const val = parseInt(stockInputs[inventoryItemId] || "");
    if (isNaN(val) || val < 0) return;
    try {
      await api.inventory.set({ inventory_item_id: inventoryItemId, location_id: selectedLocationId, available: val });
      setStockInputs((p) => ({ ...p, [inventoryItemId]: "" }));
      await loadInventory();
      toast(`Stock set to ${val}`);
    } catch { toast("Failed to set stock", "error"); }
  };

  const createProduct = async () => {
    if (!newTitle || !newHandle || !newPrice) return;
    try {
      const variant: Record<string, unknown> = {
        title: "Default",
        price: newPrice,
        barcode: newBarcode,
        pricing_type: newPricingType,
      };
      if (newPricingType === "by_weight") {
        variant.weight_unit = newWeightUnit;
        if (newMinWeight !== "") variant.min_weight_kg = newMinWeight;
        if (newMaxWeight !== "") variant.max_weight_kg = newMaxWeight;
        if (newTareWeight !== "") variant.tare_kg = newTareWeight;
      }
      const product = await api.products.create({
        title: newTitle, handle: newHandle, product_type: newType,
        variants: [variant],
      });
      if (capturedImage) {
        await api.products.uploadImage(product.id, capturedImage.blob);
        URL.revokeObjectURL(capturedImage.preview);
        setCapturedImage(null);
      }
      setNewTitle(""); setNewHandle(""); setNewType(""); setNewPrice(""); setNewBarcode("");
      setNewPricingType("fixed"); setNewWeightUnit("kg");
      setNewMinWeight(""); setNewMaxWeight(""); setNewTareWeight("");
      setShowCreate(false);
      loadProducts(); loadInventory();
      toast("Product created");
    } catch (e: any) { toast(e.message || "Failed to create product", "error"); }
  };

  const startEditVariant = (v: ProductVariant) => {
    setEditingVariantId(v.id);
    setVariantDraft(makeDraftFromVariant(v));
  };

  const cancelEditVariant = () => {
    setEditingVariantId(null);
    setVariantDraft(null);
  };

  const saveVariant = async (variantId: number) => {
    if (!variantDraft) return;
    try {
      const payload: Record<string, unknown> = {
        title: variantDraft.title,
        sku: variantDraft.sku,
        barcode: variantDraft.barcode,
        price: variantDraft.price,
        compare_at_price: variantDraft.compare_at_price === "" ? null : variantDraft.compare_at_price,
        pricing_type: variantDraft.pricing_type,
      };
      if (variantDraft.pricing_type === "by_weight") {
        payload.weight_unit = variantDraft.weight_unit;
        payload.min_weight_kg = variantDraft.min_weight_kg === "" ? null : variantDraft.min_weight_kg;
        payload.max_weight_kg = variantDraft.max_weight_kg === "" ? null : variantDraft.max_weight_kg;
        payload.tare_kg = variantDraft.tare_kg === "" ? null : variantDraft.tare_kg;
      } else {
        payload.weight_unit = null;
        payload.min_weight_kg = null;
        payload.max_weight_kg = null;
        payload.tare_kg = null;
      }
      await api.variants.update(variantId, payload);
      if (expandedId != null) {
        setExpandedProduct(await api.products.get(expandedId));
      }
      cancelEditVariant();
      toast("Variant updated");
    } catch (e: any) {
      toast(e.message || "Failed to update variant", "error");
    }
  };

  return (
    <div style={baseStyles.container}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.lg }}>
        <h2 style={{ margin: 0 }}>Products & Inventory</h2>
        <Button variant="primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "Cancel" : "+ Add Product"}
        </Button>
      </div>

      {showCreate && (
        <div style={{ ...baseStyles.card, marginBottom: spacing.lg }}>
          <h3 style={{ margin: "0 0 12px", fontSize: "15px" }}>New Product</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{ display: "flex", gap: "8px" }}>
              <input placeholder="Title *" value={newTitle} onChange={(e) => { setNewTitle(e.target.value); setNewHandle(e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")); }} style={{ ...baseStyles.input, flex: 1 }} />
              <Button variant="secondary" size="sm" onClick={() => setShowOCRScanner(true)} style={{ flexShrink: 0 }}>📷 OCR</Button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <input placeholder="Handle" value={newHandle} onChange={(e) => setNewHandle(e.target.value)} style={baseStyles.input} />
              <input placeholder="Type (e.g. dairy)" value={newType} onChange={(e) => setNewType(e.target.value)} style={baseStyles.input} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                Pricing type
                <select value={newPricingType} onChange={(e) => setNewPricingType(e.target.value as PricingType)} style={baseStyles.input}>
                  <option value="fixed">Fixed</option>
                  <option value="by_weight">By weight</option>
                </select>
              </label>
              <input
                placeholder={newPricingType === "by_weight" ? "€ per kg *" : "Price *"}
                value={newPrice}
                onChange={(e) => setNewPrice(e.target.value)}
                style={baseStyles.input}
              />
            </div>
            {newPricingType === "by_weight" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "8px" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                  Unit
                  <select value={newWeightUnit} onChange={(e) => setNewWeightUnit(e.target.value as WeightUnit)} style={baseStyles.input}>
                    <option value="kg">kg</option>
                    <option value="g">g</option>
                    <option value="100g">100g</option>
                  </select>
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                  Min weight (kg)
                  <input type="number" step="0.001" min="0" value={newMinWeight} onChange={(e) => setNewMinWeight(e.target.value)} style={baseStyles.input} />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                  Max weight (kg)
                  <input type="number" step="0.001" min="0" value={newMaxWeight} onChange={(e) => setNewMaxWeight(e.target.value)} style={baseStyles.input} />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                  Tare (kg)
                  <input type="number" step="0.001" min="0" value={newTareWeight} onChange={(e) => setNewTareWeight(e.target.value)} style={baseStyles.input} />
                </label>
              </div>
            )}
            <div style={{ display: "flex", gap: "8px" }}>
              <input placeholder="Barcode" value={newBarcode} onChange={(e) => setNewBarcode(e.target.value)} style={{ ...baseStyles.input, flex: 1 }} />
              <Button variant="secondary" size="sm" onClick={() => setShowBarcodeScanner(true)} style={{ flexShrink: 0 }}>📷 Scan</Button>
            </div>
          </div>
          <div style={{ marginTop: "10px" }}>
            {capturedImage ? (
              <div style={{ display: "flex", alignItems: "center", gap: spacing.sm }}>
                <img src={capturedImage.preview} alt="Product" style={{ width: 80, height: 80, objectFit: "cover", borderRadius: radius.sm }} />
                <Button variant="ghost" size="sm" onClick={() => { URL.revokeObjectURL(capturedImage.preview); setCapturedImage(null); }}>Remove</Button>
                <Button variant="secondary" size="sm" onClick={() => setShowCamera(true)}>Retake</Button>
              </div>
            ) : (
              <Button variant="secondary" size="sm" onClick={() => setShowCamera(true)}>📷 Add Photo</Button>
            )}
          </div>
          <Button variant="primary" onClick={createProduct} disabled={!newTitle || !newPrice} style={{ marginTop: "12px" }}>
            Create Product
          </Button>
        </div>
      )}

      {locations.length > 1 && (
        <div style={{ marginBottom: spacing.md }}>
          <label style={{ fontSize: "13px", color: colors.textSecondary, marginRight: spacing.sm }}>Location:</label>
          <select value={selectedLocationId} onChange={(e) => setSelectedLocationId(Number(e.target.value))}
            style={{ ...baseStyles.input, width: "auto", display: "inline-block" }}>
            {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        </div>
      )}
      <input placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ ...baseStyles.input, marginBottom: spacing.lg }} />

      {loading ? <Spinner label="Loading products..." /> : (
        <div style={{ ...baseStyles.card, padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
            <thead>
              <tr style={{ background: colors.surfaceMuted, textAlign: "left" }}>
                <th style={{ padding: "10px 16px" }}>Title</th>
                <th style={{ padding: "10px 16px" }}>Type</th>
                <th style={{ padding: "10px 16px" }}>Price</th>
                <th style={{ padding: "10px 16px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tbody key={p.id}>
                  <tr onClick={() => expand(p.id)} style={{ cursor: "pointer", borderBottom: `1px solid ${colors.border}`, background: expandedId === p.id ? colors.surfaceMuted : colors.surface }}>
                    <td style={{ padding: "10px 16px", fontWeight: 500 }}>{p.title}</td>
                    <td style={{ padding: "10px 16px", textTransform: "capitalize", color: colors.textSecondary }}>{p.product_type}</td>
                    <td style={{ padding: "10px 16px" }}>{p.min_price ? `$${p.min_price}` : "—"}</td>
                    <td style={{ padding: "10px 16px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: "4px", fontSize: "12px", fontWeight: 600,
                        background: p.status === "active" ? colors.successSurface : colors.surfaceMuted,
                        color: p.status === "active" ? colors.success : colors.textSecondary,
                      }}>{p.status}</span>
                    </td>
                  </tr>
                  {expandedId === p.id && expandedProduct && (
                    <tr>
                      <td colSpan={4} style={{ padding: "16px", background: colors.surfaceMuted, borderBottom: `1px solid ${colors.border}` }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                          <thead>
                            <tr style={{ textAlign: "left", color: colors.textSecondary }}>
                              <th style={{ padding: "6px 0" }}>Variant</th><th>SKU</th><th>Barcode</th><th>Pricing</th><th>Price</th><th>Stock</th><th>Set Stock</th><th>Adjust</th><th></th>
                            </tr>
                          </thead>
                          <tbody>
                            {expandedProduct.variants.map((v) => {
                              const level = Object.values(inventory).find((l) => l.inventory_item_id === v.id) || null;
                              const stock = level?.available ?? "—";
                              const isLow = level != null && level.available <= level.low_stock_threshold;
                              const isByWeight = v.pricing_type === "by_weight";
                              const priceLabel = isByWeight ? `€${v.price} / ${v.weight_unit ?? "kg"}` : `$${v.price}`;
                              const isEditing = editingVariantId === v.id && variantDraft !== null;
                              return (
                                <Fragment key={v.id}>
                                  <tr style={{ borderTop: `1px solid ${colors.border}` }}>
                                    <td style={{ padding: "8px 0" }}>{v.title}</td>
                                    <td style={{ color: colors.textSecondary }}>{v.sku || "—"}</td>
                                    <td style={{ fontFamily: "monospace", fontSize: "12px" }}>{v.barcode || "—"}</td>
                                    <td style={{ fontSize: "12px", color: colors.textSecondary }}>
                                      {isByWeight ? "by weight" : "fixed"}
                                    </td>
                                    <td>{priceLabel}</td>
                                    <td style={{ color: isLow ? colors.danger : colors.textPrimary, fontWeight: isLow ? 700 : 400 }}>
                                      {stock} {isLow && <span style={{ fontSize: "11px" }}>LOW</span>}
                                    </td>
                                    <td>
                                      {level && (
                                        <div style={{ display: "flex", gap: "4px" }}>
                                          <input
                                            placeholder="qty"
                                            value={stockInputs[level.inventory_item_id] || ""}
                                            onChange={(e) => setStockInputs((prev) => ({ ...prev, [level.inventory_item_id]: e.target.value }))}
                                            onKeyDown={(e) => e.key === "Enter" && setStock(level.inventory_item_id)}
                                            style={{ ...baseStyles.input, width: 60, padding: "4px 6px", fontSize: "12px" }}
                                          />
                                          <Button variant="secondary" size="sm" onClick={() => setStock(level.inventory_item_id)}>Set</Button>
                                        </div>
                                      )}
                                    </td>
                                    <td>
                                      {level && (
                                        <div style={{ display: "flex", gap: "4px" }}>
                                          <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, -1); }}>-1</Button>
                                          <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, 1); }}>+1</Button>
                                          <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, 10); }}>+10</Button>
                                        </div>
                                      )}
                                    </td>
                                    <td>
                                      {isEditing ? (
                                        <Button variant="ghost" size="sm" onClick={cancelEditVariant}>Cancel</Button>
                                      ) : (
                                        <div style={{ display: "flex", gap: "4px" }}>
                                          <Button variant="secondary" size="sm" onClick={() => startEditVariant(v)}>Edit</Button>
                                          <Button variant="secondary" size="sm" onClick={() => setVariantForModal({
                                            id: v.id, product_id: v.product_id, title: v.title,
                                            sku: v.sku || null, barcode: v.barcode || null,
                                            price: v.price, pricing_type: (v.pricing_type ?? "fixed") as "fixed" | "by_weight" | "by_volume",
                                            vat_rate: "19.00",
                                            min_weight_kg: v.min_weight_kg ?? null,
                                            max_weight_kg: v.max_weight_kg ?? null,
                                            tare_kg: v.tare_kg ?? null,
                                          })}>Modal Edit</Button>
                                        </div>
                                      )}
                                    </td>
                                  </tr>
                                  {isEditing && variantDraft && (
                                    <tr>
                                      <td colSpan={9} style={{ padding: "12px 8px", background: colors.surface, borderTop: `1px solid ${colors.border}` }}>
                                        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px" }}>
                                            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                              Title
                                              <input value={variantDraft.title} onChange={(e) => setVariantDraft({ ...variantDraft, title: e.target.value })} style={baseStyles.input} />
                                            </label>
                                            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                              SKU
                                              <input value={variantDraft.sku} onChange={(e) => setVariantDraft({ ...variantDraft, sku: e.target.value })} style={baseStyles.input} />
                                            </label>
                                            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                              Barcode
                                              <input value={variantDraft.barcode} onChange={(e) => setVariantDraft({ ...variantDraft, barcode: e.target.value })} style={baseStyles.input} />
                                            </label>
                                          </div>
                                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px" }}>
                                            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                              Pricing type
                                              <select
                                                value={variantDraft.pricing_type}
                                                onChange={(e) => setVariantDraft({ ...variantDraft, pricing_type: e.target.value as PricingType })}
                                                style={baseStyles.input}
                                              >
                                                <option value="fixed">Fixed</option>
                                                <option value="by_weight">By weight</option>
                                              </select>
                                            </label>
                                            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                              {variantDraft.pricing_type === "by_weight" ? "€ per kg" : "€"}
                                              <input type="number" step="0.01" min="0" value={variantDraft.price} onChange={(e) => setVariantDraft({ ...variantDraft, price: e.target.value })} style={baseStyles.input} />
                                            </label>
                                            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                              Compare-at price
                                              <input type="number" step="0.01" min="0" value={variantDraft.compare_at_price} onChange={(e) => setVariantDraft({ ...variantDraft, compare_at_price: e.target.value })} style={baseStyles.input} />
                                            </label>
                                          </div>
                                          {variantDraft.pricing_type === "by_weight" && (
                                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "8px" }}>
                                              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                                Weight unit
                                                <select value={variantDraft.weight_unit} onChange={(e) => setVariantDraft({ ...variantDraft, weight_unit: e.target.value as WeightUnit })} style={baseStyles.input}>
                                                  <option value="kg">kg</option>
                                                  <option value="g">g</option>
                                                  <option value="100g">100g</option>
                                                </select>
                                              </label>
                                              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                                Min weight (kg)
                                                <input type="number" step="0.001" min="0" value={variantDraft.min_weight_kg} onChange={(e) => setVariantDraft({ ...variantDraft, min_weight_kg: e.target.value })} style={baseStyles.input} />
                                              </label>
                                              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                                Max weight (kg)
                                                <input type="number" step="0.001" min="0" value={variantDraft.max_weight_kg} onChange={(e) => setVariantDraft({ ...variantDraft, max_weight_kg: e.target.value })} style={baseStyles.input} />
                                              </label>
                                              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px", color: colors.textSecondary }}>
                                                Tare (kg)
                                                <input type="number" step="0.001" min="0" value={variantDraft.tare_kg} onChange={(e) => setVariantDraft({ ...variantDraft, tare_kg: e.target.value })} style={baseStyles.input} />
                                              </label>
                                            </div>
                                          )}
                                          <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                                            <Button variant="ghost" size="sm" onClick={cancelEditVariant}>Cancel</Button>
                                            <Button variant="primary" size="sm" onClick={() => saveVariant(v.id)}>Save variant</Button>
                                          </div>
                                        </div>
                                      </td>
                                    </tr>
                                  )}
                                </Fragment>
                              );
                            })}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </tbody>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {showBarcodeScanner && (
        <BarcodeScanner
          onDetected={(code) => { setNewBarcode(code); setShowBarcodeScanner(false); }}
          onClose={() => setShowBarcodeScanner(false)}
        />
      )}
      {showOCRScanner && (
        <OCRScanner
          label="Scan Product Name"
          onDetected={(text) => { setNewTitle(text); setNewHandle(text.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")); setShowOCRScanner(false); }}
          onClose={() => setShowOCRScanner(false)}
        />
      )}
      {showCamera && (
        <CameraCapture
          onCapture={(blob) => {
            setCapturedImage({ blob, preview: URL.createObjectURL(blob) });
            setShowCamera(false);
          }}
          onClose={() => setShowCamera(false)}
        />
      )}
      {variantForModal && (
        <VariantEditModal
          initial={variantForModal}
          onSaved={async () => {
            setVariantForModal(null);
            if (expandedId != null) setExpandedProduct(await api.products.get(expandedId));
            toast("Variant updated");
          }}
          onCancel={() => setVariantForModal(null)}
        />
      )}
    </div>
  );
}
