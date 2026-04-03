import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket, Spinner, Button, colors, baseStyles, spacing, radius, shadow } from "@openmarket/shared";
import type { Product, ProductListWithPrice } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

export function ShopPage() {
  const [products, setProducts] = useState<ProductListWithPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const { addItem } = useCart();

  const productTypes = [...new Set(products.map((p) => p.product_type).filter(Boolean))].sort();

  useEffect(() => {
    setLoading(true);
    api.products.list({
      status: "active",
      search: search || undefined,
      product_type: selectedType || undefined,
    })
      .then(setProducts)
      .finally(() => setLoading(false));
  }, [search, selectedType]);

  const handleInventoryUpdate = useCallback(() => {}, []);
  useWebSocket(handleInventoryUpdate);

  const openProduct = async (id: number) => {
    setDetailLoading(true);
    const product = await api.products.get(id);
    setSelectedProduct(product);
    setDetailLoading(false);
  };

  return (
    <div style={{ ...baseStyles.container, display: "flex", gap: spacing.lg }}>
      {/* Sidebar */}
      <div style={{ width: 180, flexShrink: 0 }}>
        <h3 style={{ fontSize: "14px", color: colors.textSecondary, marginBottom: spacing.sm, textTransform: "uppercase", letterSpacing: "0.5px" }}>
          Categories
        </h3>
        <div onClick={() => setSelectedType(null)} style={{
          padding: "6px 10px", cursor: "pointer", borderRadius: radius.sm, fontSize: "14px", marginBottom: "2px",
          background: selectedType === null ? colors.brandLight : "transparent",
          color: selectedType === null ? colors.brand : colors.textPrimary,
          fontWeight: selectedType === null ? 600 : 400,
        }}>All Products</div>
        {productTypes.map((t) => (
          <div key={t} onClick={() => setSelectedType(t)} style={{
            padding: "6px 10px", cursor: "pointer", borderRadius: radius.sm, fontSize: "14px", marginBottom: "2px", textTransform: "capitalize",
            background: selectedType === t ? colors.brandLight : "transparent",
            color: selectedType === t ? colors.brand : colors.textPrimary,
            fontWeight: selectedType === t ? 600 : 400,
          }}>{t}</div>
        ))}
      </div>

      {/* Main */}
      <div style={{ flex: 1 }}>
        <input type="text" placeholder="Search products..." value={search} onChange={(e) => setSearch(e.target.value)}
          style={{ ...baseStyles.input, marginBottom: spacing.lg }} />

        {loading ? (
          <Spinner label="Loading products..." />
        ) : products.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: colors.textSecondary }}>
            <p style={{ fontSize: "16px" }}>No products found</p>
            <p style={{ fontSize: "14px" }}>Try a different search or category</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: spacing.md }}>
            {products.map((p) => (
              <div key={p.id} onClick={() => openProduct(p.id)}
                style={{ ...baseStyles.card, cursor: "pointer", transition: "box-shadow 0.15s, border-color 0.15s" }}
                onMouseEnter={(e) => { e.currentTarget.style.boxShadow = shadow.md; e.currentTarget.style.borderColor = colors.borderStrong; }}
                onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "none"; e.currentTarget.style.borderColor = colors.border; }}>
                <div style={{ fontSize: "12px", color: colors.textSecondary, textTransform: "capitalize", marginBottom: "4px" }}>{p.product_type}</div>
                <h3 style={{ margin: "0 0 8px", fontSize: "15px", fontWeight: 600 }}>{p.title}</h3>
                {p.min_price && <div style={{ fontSize: "16px", fontWeight: 700, color: colors.brand }}>${p.min_price}</div>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail Panel */}
      {(selectedProduct || detailLoading) && (
        <div style={{ width: 320, flexShrink: 0, ...baseStyles.card, alignSelf: "flex-start", position: "sticky" as const, top: `calc(${spacing.lg} + 56px)` }}>
          {detailLoading ? <Spinner label="Loading..." /> : selectedProduct && (
            <>
              <h2 style={{ margin: "0 0 4px", fontSize: "18px" }}>{selectedProduct.title}</h2>
              {selectedProduct.description && <p style={{ color: colors.textSecondary, fontSize: "14px", margin: "0 0 16px" }}>{selectedProduct.description}</p>}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {selectedProduct.variants.map((v) => (
                  <div key={v.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px", background: colors.surfaceMuted, borderRadius: radius.sm }}>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: "14px" }}>{v.title}</div>
                      <div style={{ fontSize: "15px", fontWeight: 700, color: colors.brand }}>${v.price}</div>
                    </div>
                    <Button variant="primary" size="sm" onClick={() => addItem(selectedProduct, v)}>Add</Button>
                  </div>
                ))}
              </div>
              <Button variant="ghost" size="sm" onClick={() => setSelectedProduct(null)} style={{ marginTop: "12px", width: "100%" }}>Close</Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
