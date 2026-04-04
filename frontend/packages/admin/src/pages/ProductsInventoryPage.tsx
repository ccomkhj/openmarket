import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket, Button, Spinner, colors, baseStyles, spacing, radius } from "@openmarket/shared";
import type { Product, ProductListWithPrice, InventoryLevel } from "@openmarket/shared";

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
  const [stockInputs, setStockInputs] = useState<Record<number, string>>({});

  const loadProducts = async () => {
    setLoading(true);
    const prods = await api.products.list({ search: search || undefined });
    setProducts(prods);
    setLoading(false);
  };

  const loadInventory = async () => {
    const levels = await api.inventory.levels(1);
    const map: Record<number, InventoryLevel> = {};
    for (const l of levels) map[l.inventory_item_id] = l;
    setInventory(map);
  };

  useEffect(() => { loadProducts(); loadInventory(); }, [search]);

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
    await api.inventory.adjust({ inventory_item_id: inventoryItemId, location_id: 1, available_adjustment: delta });
    await loadInventory();
  };

  const setStock = async (inventoryItemId: number) => {
    const val = parseInt(stockInputs[inventoryItemId] || "");
    if (isNaN(val) || val < 0) return;
    await api.inventory.set({ inventory_item_id: inventoryItemId, location_id: 1, available: val });
    setStockInputs((p) => ({ ...p, [inventoryItemId]: "" }));
    await loadInventory();
  };

  const createProduct = async () => {
    if (!newTitle || !newHandle || !newPrice) return;
    await api.products.create({
      title: newTitle, handle: newHandle, product_type: newType,
      variants: [{ title: "Default", price: newPrice, barcode: newBarcode }],
    });
    setNewTitle(""); setNewHandle(""); setNewType(""); setNewPrice(""); setNewBarcode("");
    setShowCreate(false);
    loadProducts(); loadInventory();
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
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <input placeholder="Title *" value={newTitle} onChange={(e) => { setNewTitle(e.target.value); setNewHandle(e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")); }} style={baseStyles.input} />
            <input placeholder="Handle" value={newHandle} onChange={(e) => setNewHandle(e.target.value)} style={baseStyles.input} />
            <input placeholder="Type (e.g. dairy)" value={newType} onChange={(e) => setNewType(e.target.value)} style={baseStyles.input} />
            <input placeholder="Price *" value={newPrice} onChange={(e) => setNewPrice(e.target.value)} style={baseStyles.input} />
            <input placeholder="Barcode" value={newBarcode} onChange={(e) => setNewBarcode(e.target.value)} style={baseStyles.input} />
          </div>
          <Button variant="primary" onClick={createProduct} disabled={!newTitle || !newPrice} style={{ marginTop: "12px" }}>
            Create Product
          </Button>
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
                              <th style={{ padding: "6px 0" }}>Variant</th><th>SKU</th><th>Barcode</th><th>Price</th><th>Stock</th><th>Set Stock</th><th>Adjust</th>
                            </tr>
                          </thead>
                          <tbody>
                            {expandedProduct.variants.map((v) => {
                              const level = Object.values(inventory).find((l) => l.inventory_item_id === v.id) || null;
                              const stock = level?.available ?? "—";
                              const isLow = level != null && level.available <= level.low_stock_threshold;
                              return (
                                <tr key={v.id} style={{ borderTop: `1px solid ${colors.border}` }}>
                                  <td style={{ padding: "8px 0" }}>{v.title}</td>
                                  <td style={{ color: colors.textSecondary }}>{v.sku || "—"}</td>
                                  <td style={{ fontFamily: "monospace", fontSize: "12px" }}>{v.barcode || "—"}</td>
                                  <td>${v.price}</td>
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
                                </tr>
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
    </div>
  );
}
