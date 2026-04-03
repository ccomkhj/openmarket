import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket } from "@openmarket/shared";
import type { Product, ProductListItem } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

export function ShopPage() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [search, setSearch] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const { addItem } = useCart();

  useEffect(() => {
    api.products.list({ status: "active", search: search || undefined }).then(setProducts);
  }, [search]);

  const handleInventoryUpdate = useCallback(() => {}, []);
  useWebSocket(handleInventoryUpdate);

  const openProduct = async (id: number) => {
    const product = await api.products.get(id);
    setSelectedProduct(product);
  };

  return (
    <div style={{ display: "flex", padding: "1rem", gap: "1rem" }}>
      <div style={{ flex: 1 }}>
        <input type="text" placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)}
          style={{ width: "100%", padding: "0.5rem", marginBottom: "1rem", boxSizing: "border-box" }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "1rem" }}>
          {products.map((p) => (
            <div key={p.id} onClick={() => openProduct(p.id)}
              style={{ border: "1px solid #ddd", padding: "1rem", cursor: "pointer", borderRadius: "4px" }}>
              <h3 style={{ margin: "0 0 0.5rem" }}>{p.title}</h3>
              <p style={{ margin: 0, color: "#666" }}>{p.product_type}</p>
            </div>
          ))}
        </div>
      </div>
      {selectedProduct && (
        <div style={{ width: 300, border: "1px solid #ddd", padding: "1rem", borderRadius: "4px" }}>
          <h2>{selectedProduct.title}</h2>
          <p>{selectedProduct.description}</p>
          <h4>Variants:</h4>
          {selectedProduct.variants.map((v) => (
            <div key={v.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
              <span>{v.title} - ${v.price}</span>
              <button onClick={() => addItem(selectedProduct, v)}>Add</button>
            </div>
          ))}
          <button onClick={() => setSelectedProduct(null)} style={{ marginTop: "1rem" }}>Close</button>
        </div>
      )}
    </div>
  );
}
