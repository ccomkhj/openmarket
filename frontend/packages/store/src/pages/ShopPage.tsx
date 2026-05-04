import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  useWebSocket,
  useDebounce,
  Skeleton,
  Button,
  colors,
  baseStyles,
  spacing,
  radius,
  shadow,
  useToast,
} from "@openmarket/shared";
import type { Product, ProductListWithPrice, ProductVariant } from "@openmarket/shared";
import { useCart } from "../store/cartStore";
import { usePageMeta } from "../hooks/usePageMeta";
import { useIsMobile } from "../hooks/useIsMobile";

const SORT_OPTIONS = [
  { value: "", label: "Default" },
  { value: "title", label: "Name A-Z" },
  { value: "price_asc", label: "Price: Low to High" },
  { value: "price_desc", label: "Price: High to Low" },
  { value: "newest", label: "Newest" },
];

export function ShopPage() {
  const [products, setProducts] = useState<ProductListWithPrice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [quickAddBusyId, setQuickAddBusyId] = useState<number | null>(null);

  const { addItem } = useCart();
  const { toast } = useToast();
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const debouncedSearch = useDebounce(search, 300);

  usePageMeta(selectedType ? `${selectedType}` : "Shop", "Browse products at OpenMarket.");

  const productTypes = useMemo(
    () => [...new Set(products.map((p) => p.product_type).filter(Boolean))].sort(),
    [products],
  );

  useEffect(() => {
    setLoading(true);
    setError("");
    api.products.list({
      status: "active",
      search: debouncedSearch || undefined,
      product_type: selectedType || undefined,
      sort_by: sortBy || undefined,
    })
      .then(setProducts)
      .catch(() => setError("Failed to load products. Please try again."))
      .finally(() => setLoading(false));
  }, [debouncedSearch, selectedType, sortBy]);

  const refetch = useCallback(() => {
    api.products.list({
      status: "active",
      search: debouncedSearch || undefined,
      product_type: selectedType || undefined,
      sort_by: sortBy || undefined,
    })
      .then(setProducts)
      .catch(() => {});
  }, [debouncedSearch, selectedType, sortBy]);

  // Coalesce a burst of inventory events (e.g. a 10-line POS sale) into one refetch.
  const refetchTimer = useRef<number | null>(null);
  const handleInventoryUpdate = useCallback(() => {
    if (refetchTimer.current) window.clearTimeout(refetchTimer.current);
    refetchTimer.current = window.setTimeout(() => { refetch(); }, 400);
  }, [refetch]);
  useEffect(() => () => {
    if (refetchTimer.current) window.clearTimeout(refetchTimer.current);
  }, []);
  useWebSocket(handleInventoryUpdate);

  const quickAdd = async (e: React.MouseEvent, p: ProductListWithPrice) => {
    e.stopPropagation();
    e.preventDefault();
    if (p.total_stock === 0) {
      toast("Sold out", "error");
      return;
    }
    setQuickAddBusyId(p.id);
    try {
      const full: Product = await api.products.get(p.id);
      const firstVariant: ProductVariant | undefined = full.variants[0];
      if (!firstVariant) {
        toast("This product is unavailable", "error");
        return;
      }
      if (firstVariant.available === 0) {
        toast("Sold out", "error");
        return;
      }
      addItem(full, firstVariant);
      toast(`Added ${full.title} to cart`, "success");
    } catch {
      toast("Couldn’t add to cart. Try again.", "error");
    } finally {
      setQuickAddBusyId(null);
    }
  };

  const renderCategoryList = (
    <>
      <h3 style={{
        fontSize: "14px", color: colors.textSecondary,
        marginTop: 0, marginBottom: spacing.sm,
        textTransform: "uppercase", letterSpacing: "0.5px",
      }}>
        Categories
      </h3>
      <div onClick={() => { setSelectedType(null); setFiltersOpen(false); }} style={{
        padding: "8px 10px", cursor: "pointer", borderRadius: radius.sm, fontSize: "14px", marginBottom: 2,
        background: selectedType === null ? colors.brandLight : "transparent",
        color: selectedType === null ? colors.brand : colors.textPrimary,
        fontWeight: selectedType === null ? 600 : 400,
      }}>All Products</div>
      {productTypes.map((t) => (
        <div key={t} onClick={() => { setSelectedType(t); setFiltersOpen(false); }} style={{
          padding: "8px 10px", cursor: "pointer", borderRadius: radius.sm,
          fontSize: "14px", marginBottom: 2, textTransform: "capitalize",
          background: selectedType === t ? colors.brandLight : "transparent",
          color: selectedType === t ? colors.brand : colors.textPrimary,
          fontWeight: selectedType === t ? 600 : 400,
        }}>{t}</div>
      ))}
    </>
  );

  return (
    <div style={{
      ...baseStyles.container,
      display: "flex",
      flexDirection: isMobile ? "column" : "row",
      gap: isMobile ? spacing.md : spacing.lg,
    }}>
      {/* Sidebar (desktop) */}
      {!isMobile && (
        <div style={{ width: 180, flexShrink: 0 }}>
          {renderCategoryList}
        </div>
      )}

      {/* Mobile filter toggle + collapsible panel */}
      {isMobile && (
        <div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setFiltersOpen((o) => !o)}
            style={{ width: "100%" }}
          >
            {filtersOpen ? "Hide filters ▴" : `Filters${selectedType ? ` · ${selectedType}` : ""} ▾`}
          </Button>
          {filtersOpen && (
            <div style={{
              ...baseStyles.card,
              padding: spacing.md,
              marginTop: spacing.sm,
            }}>
              {renderCategoryList}
            </div>
          )}
        </div>
      )}

      {/* Main */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          gap: spacing.sm,
          marginBottom: spacing.lg,
        }}>
          <input
            type="text"
            placeholder="Search products..."
            aria-label="Search products"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ ...baseStyles.input, flex: 1 }}
          />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            aria-label="Sort products"
            style={{
              ...baseStyles.input,
              width: isMobile ? "100%" : "auto",
              minWidth: isMobile ? undefined : 160,
              cursor: "pointer",
            }}
          >
            {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {error && (
          <div style={{
            background: colors.dangerSurface, color: colors.danger,
            padding: "10px 14px", borderRadius: radius.sm,
            fontSize: "14px", marginBottom: spacing.md,
          }}>
            {error}
            <Button variant="ghost" size="sm" onClick={() => setError("")} style={{ marginLeft: spacing.sm }}>
              Dismiss
            </Button>
          </div>
        )}

        {loading ? (
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(auto-fill, minmax(${isMobile ? "150px" : "220px"}, 1fr))`,
            gap: spacing.md,
          }}>
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} style={{ ...baseStyles.card, padding: 0, overflow: "hidden" }}>
                <Skeleton height={160} style={{ borderRadius: 0 }} />
                <div style={{ padding: spacing.md }}>
                  <Skeleton height={10} width="40%" style={{ marginBottom: 8 }} />
                  <Skeleton height={14} width="80%" style={{ marginBottom: 8 }} />
                  <Skeleton height={16} width="30%" />
                </div>
              </div>
            ))}
          </div>
        ) : products.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: colors.textSecondary }}>
            <p style={{ fontSize: "16px" }}>No products found</p>
            <p style={{ fontSize: "14px" }}>Try a different search or category</p>
          </div>
        ) : (
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(auto-fill, minmax(${isMobile ? "150px" : "220px"}, 1fr))`,
            gap: spacing.md,
          }}>
            {products.map((p) => (
              <div
                key={p.id}
                onClick={(e) => {
                  // Ignore clicks that originated on an interactive child (e.g. quick-add).
                  if (e.target !== e.currentTarget && (e.target as HTMLElement).closest("button")) return;
                  navigate(`/product/${p.id}`);
                }}
                role="link"
                tabIndex={0}
                onKeyDown={(e) => {
                  // Don't hijack Enter/Space when focus is on an inner control.
                  if (e.target !== e.currentTarget) return;
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    navigate(`/product/${p.id}`);
                  }
                }}
                style={{
                  ...baseStyles.card,
                  cursor: "pointer",
                  transition: "box-shadow 0.15s, border-color 0.15s, outline-color 0.15s",
                  padding: 0,
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                  outline: "2px solid transparent",
                  outlineOffset: 2,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = shadow.md;
                  e.currentTarget.style.borderColor = colors.borderStrong;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = "none";
                  e.currentTarget.style.borderColor = colors.border;
                }}
                onFocus={(e) => {
                  e.currentTarget.style.outlineColor = colors.brand;
                  e.currentTarget.style.boxShadow = shadow.md;
                }}
                onBlur={(e) => {
                  e.currentTarget.style.outlineColor = "transparent";
                  e.currentTarget.style.boxShadow = "none";
                }}
              >
                <div style={{ position: "relative" }}>
                  {p.image_url ? (
                    <img
                      src={p.image_url}
                      alt={p.title}
                      loading="lazy"
                      style={{
                        width: "100%",
                        aspectRatio: "1 / 1",
                        objectFit: "cover",
                        display: "block",
                        opacity: p.total_stock === 0 ? 0.55 : 1,
                      }}
                    />
                  ) : (
                    <div style={{
                      width: "100%",
                      aspectRatio: "1 / 1",
                      background: colors.surfaceMuted,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      color: colors.textSecondary, fontSize: "13px",
                    }}>No image</div>
                  )}
                  {p.total_stock === 0 && (
                    <span style={{
                      position: "absolute", top: 8, left: 8,
                      background: colors.surface, color: colors.textPrimary,
                      border: `1px solid ${colors.borderStrong}`,
                      fontSize: "11px", fontWeight: 700,
                      padding: "3px 8px", borderRadius: radius.sm,
                      textTransform: "uppercase", letterSpacing: "0.5px",
                    }}>Sold out</span>
                  )}
                  {p.total_stock !== 0 && p.total_stock != null && p.total_stock <= 5 && (
                    <span style={{
                      position: "absolute", top: 8, left: 8,
                      background: colors.warningSurface, color: colors.warning,
                      fontSize: "11px", fontWeight: 700,
                      padding: "3px 8px", borderRadius: radius.sm,
                      textTransform: "uppercase", letterSpacing: "0.5px",
                    }}>Only {p.total_stock} left</span>
                  )}
                </div>
                <div style={{ padding: spacing.md, flex: 1, display: "flex", flexDirection: "column" }}>
                  <div style={{
                    fontSize: "12px",
                    color: colors.textSecondary,
                    textTransform: "capitalize",
                    marginBottom: 4,
                  }}>{p.product_type}</div>
                  <h3 style={{
                    margin: "0 0 8px",
                    fontSize: isMobile ? "14px" : "15px",
                    fontWeight: 600,
                    lineHeight: 1.3,
                  }}>{p.title}</h3>
                  {p.min_price && (
                    <div style={{
                      fontSize: isMobile ? "15px" : "16px",
                      fontWeight: 700,
                      color: colors.brand,
                      marginTop: "auto",
                    }}>${p.min_price}</div>
                  )}
                  <Button
                    variant="secondary"
                    size="sm"
                    fullWidth
                    loading={quickAddBusyId === p.id}
                    disabled={p.total_stock === 0}
                    onClick={(e) => quickAdd(e, p)}
                    style={{ marginTop: spacing.sm }}
                  >
                    {p.total_stock === 0 ? "Sold out" : "Add to cart"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
