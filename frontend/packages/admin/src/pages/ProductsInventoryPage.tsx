import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket } from "@openmarket/shared";
import type { Product, ProductListItem, InventoryLevel } from "@openmarket/shared";

export function ProductsInventoryPage() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [inventory, setInventory] = useState<Record<number, InventoryLevel>>({});
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedProduct, setExpandedProduct] = useState<Product | null>(null);

  const loadProducts = async () => { setProducts(await api.products.list()); };
  const loadInventory = async () => {
    const levels = await api.inventory.levels(1);
    const map: Record<number, InventoryLevel> = {};
    for (const l of levels) map[l.inventory_item_id] = l;
    setInventory(map);
  };

  useEffect(() => { loadProducts(); loadInventory(); }, []);

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

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Products & Inventory</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead><tr style={{ borderBottom: "2px solid #333", textAlign: "left" }}>
          <th style={{ padding: "0.5rem" }}>Title</th><th>Type</th><th>Status</th><th>Tags</th>
        </tr></thead>
        <tbody>
          {products.map((p) => (
            <tr key={p.id}>
              <td colSpan={4} style={{ padding: 0 }}>
                <div onClick={() => expand(p.id)} style={{ display: "flex", cursor: "pointer", padding: "0.5rem", borderBottom: "1px solid #eee", background: expandedId === p.id ? "#f9f9f9" : "transparent" }}>
                  <span style={{ flex: 1 }}>{p.title}</span>
                  <span style={{ flex: 1 }}>{p.product_type}</span>
                  <span style={{ flex: 1 }}>{p.status}</span>
                  <span style={{ flex: 1 }}>{p.tags.join(", ")}</span>
                </div>
                {expandedId === p.id && expandedProduct && (
                  <div style={{ padding: "1rem", background: "#f5f5f5" }}>
                    <h4>Variants</h4>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead><tr style={{ textAlign: "left" }}><th>Variant</th><th>SKU</th><th>Barcode</th><th>Price</th><th>Stock</th><th>Actions</th></tr></thead>
                      <tbody>
                        {expandedProduct.variants.map((v) => {
                          const level = Object.values(inventory).find((l) => l.inventory_item_id === v.id) || null;
                          const stock = level?.available ?? "?";
                          const isLow = level != null && level.available <= level.low_stock_threshold;
                          return (
                            <tr key={v.id}>
                              <td>{v.title}</td><td>{v.sku}</td><td>{v.barcode}</td><td>${v.price}</td>
                              <td style={{ color: isLow ? "red" : "inherit", fontWeight: isLow ? "bold" : "normal" }}>{stock} {isLow && "(LOW)"}</td>
                              <td>{level && (<>
                                <button onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, -1); }}>-1</button>
                                <button onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, 1); }}>+1</button>
                                <button onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, 10); }}>+10</button>
                              </>)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
