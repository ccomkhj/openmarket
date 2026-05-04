import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  api,
  Button,
  Spinner,
  baseStyles,
  colors,
  radius,
  shadow,
  spacing,
  useToast,
  useWebSocket,
} from "@openmarket/shared";
import type { Product, ProductVariant } from "@openmarket/shared";
import { useCart } from "../store/cartStore";
import { usePageMeta } from "../hooks/usePageMeta";
import { useIsMobile } from "../hooks/useIsMobile";

interface InventoryEvent {
  inventory_item_id: number;
  location_id: number;
  available: number;
}

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const productId = id ? Number(id) : NaN;
  const isMobile = useIsMobile();
  const { addItem } = useCart();
  const { toast } = useToast();

  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeImage, setActiveImage] = useState(0);
  const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null);

  useEffect(() => {
    if (!Number.isFinite(productId)) {
      setError("Invalid product link.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    api.products
      .get(productId)
      .then((p) => {
        setProduct(p);
        setSelectedVariantId(p.variants[0]?.id ?? null);
        setActiveImage(0);
      })
      .catch(() => setError("We couldn’t load this product."))
      .finally(() => setLoading(false));
  }, [productId]);

  usePageMeta(
    product?.title ?? (loading ? "Loading product…" : "Product not found"),
    product?.description || undefined,
  );

  const selectedVariant: ProductVariant | undefined = product?.variants.find(
    (v) => v.id === selectedVariantId,
  );

  const handleInventoryUpdate = useCallback((evt: InventoryEvent) => {
    setProduct((prev) => {
      if (!prev) return prev;
      const idx = prev.variants.findIndex(
        (v) => v.inventory_item_id != null && v.inventory_item_id === evt.inventory_item_id,
      );
      if (idx === -1) return prev;
      const variants = prev.variants.slice();
      variants[idx] = { ...variants[idx], available: evt.available };
      return { ...prev, variants };
    });
  }, []);
  useWebSocket(handleInventoryUpdate);

  const available = selectedVariant?.available;
  const lowThreshold = selectedVariant?.low_stock_threshold ?? 5;
  const soldOut = available === 0;
  const lowStock = typeof available === "number" && available > 0 && available <= lowThreshold;

  const handleAdd = () => {
    if (!product || !selectedVariant) return;
    if (soldOut) {
      toast("Sold out", "error");
      return;
    }
    addItem(product, selectedVariant);
    toast(`Added ${product.title} to cart`, "success");
  };

  if (loading) {
    return (
      <div style={{ ...baseStyles.container, paddingTop: spacing.xl }}>
        <Spinner label="Loading product..." />
      </div>
    );
  }

  if (error || !product) {
    return (
      <div style={{ ...baseStyles.container, maxWidth: 600, paddingTop: spacing.xl }}>
        <div style={{ ...baseStyles.card, textAlign: "center" }}>
          <p style={{ color: colors.textSecondary, fontSize: "16px" }}>
            {error || "Product not found."}
          </p>
          <Button variant="primary" onClick={() => navigate("/")} style={{ marginTop: spacing.md }}>
            Back to Shop
          </Button>
        </div>
      </div>
    );
  }

  const images = product.images.slice().sort((a, b) => a.position - b.position);
  const mainImage = images[activeImage];
  const compareAt = selectedVariant?.compare_at_price
    ? parseFloat(selectedVariant.compare_at_price)
    : null;
  const price = selectedVariant ? parseFloat(selectedVariant.price) : 0;
  const onSale = compareAt !== null && compareAt > price;

  return (
    <div style={{ ...baseStyles.container, maxWidth: 1100 }}>
      <Link
        to="/"
        style={{
          color: colors.textSecondary,
          fontSize: "14px",
          textDecoration: "none",
          display: "inline-block",
          marginBottom: spacing.md,
        }}
      >
        ← Back to Shop
      </Link>

      <div
        style={{
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          gap: isMobile ? spacing.lg : spacing.xl,
        }}
      >
        {/* Gallery */}
        <div style={{ flex: isMobile ? "unset" : "1 1 48%", maxWidth: isMobile ? "100%" : "48%" }}>
          <div
            style={{
              width: "100%",
              aspectRatio: "1 / 1",
              background: colors.surfaceMuted,
              borderRadius: radius.md,
              overflow: "hidden",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: `1px solid ${colors.border}`,
            }}
          >
            {mainImage ? (
              <img
                src={mainImage.src}
                alt={product.title}
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
            ) : (
              <span style={{ color: colors.textSecondary, fontSize: "14px" }}>No image</span>
            )}
          </div>
          {images.length > 1 && (
            <div
              style={{
                display: "flex",
                gap: spacing.sm,
                marginTop: spacing.sm,
                overflowX: "auto",
                paddingBottom: 4,
              }}
            >
              {images.map((img, i) => (
                <button
                  key={img.id}
                  onClick={() => setActiveImage(i)}
                  aria-label={`Show image ${i + 1}`}
                  style={{
                    flexShrink: 0,
                    width: 64,
                    height: 64,
                    border: `2px solid ${i === activeImage ? colors.brand : colors.border}`,
                    borderRadius: radius.sm,
                    padding: 0,
                    overflow: "hidden",
                    background: colors.surface,
                    cursor: "pointer",
                  }}
                >
                  <img
                    src={img.src}
                    alt=""
                    style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Info */}
        <div style={{ flex: 1 }}>
          {product.product_type && (
            <div
              style={{
                fontSize: "12px",
                color: colors.textSecondary,
                textTransform: "uppercase",
                letterSpacing: "0.5px",
                marginBottom: 6,
              }}
            >
              {product.product_type}
            </div>
          )}
          <h1 style={{ margin: 0, fontSize: isMobile ? "22px" : "26px", fontWeight: 700 }}>
            {product.title}
          </h1>

          <div style={{ display: "flex", alignItems: "baseline", gap: spacing.sm, marginTop: spacing.md, flexWrap: "wrap" }}>
            <span style={{ fontSize: "26px", fontWeight: 700, color: colors.brand }}>
              ${price.toFixed(2)}
            </span>
            {onSale && compareAt !== null && (
              <>
                <span
                  style={{
                    fontSize: "16px",
                    color: colors.textSecondary,
                    textDecoration: "line-through",
                  }}
                >
                  ${compareAt.toFixed(2)}
                </span>
                <span
                  style={{
                    background: colors.dangerSurface,
                    color: colors.danger,
                    fontSize: "12px",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: radius.sm,
                  }}
                >
                  {Math.round(((compareAt - price) / compareAt) * 100)}% off
                </span>
              </>
            )}
          </div>

          <div style={{ marginTop: spacing.sm }}>
            {soldOut && (
              <span style={{
                background: colors.surfaceMuted, color: colors.textPrimary,
                border: `1px solid ${colors.borderStrong}`,
                fontSize: "12px", fontWeight: 700,
                padding: "3px 10px", borderRadius: radius.sm,
                textTransform: "uppercase", letterSpacing: "0.5px",
              }}>Sold out</span>
            )}
            {lowStock && (
              <span style={{
                background: colors.warningSurface, color: colors.warning,
                fontSize: "12px", fontWeight: 700,
                padding: "3px 10px", borderRadius: radius.sm,
                textTransform: "uppercase", letterSpacing: "0.5px",
              }}>Only {available} left</span>
            )}
            {!soldOut && !lowStock && typeof available === "number" && (
              <span style={{ fontSize: "13px", color: colors.success, fontWeight: 600 }}>
                In stock
              </span>
            )}
          </div>

          {product.description && (
            <p
              style={{
                marginTop: spacing.md,
                color: colors.textSecondary,
                fontSize: "14px",
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
              }}
            >
              {product.description}
            </p>
          )}

          {product.variants.length > 1 && (
            <div style={{ marginTop: spacing.lg }}>
              <div
                id="variant-group-label"
                style={{
                  fontSize: "13px",
                  fontWeight: 600,
                  color: colors.textSecondary,
                  marginBottom: spacing.sm,
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                }}
              >
                Options
              </div>
              <div
                role="radiogroup"
                aria-labelledby="variant-group-label"
                style={{ display: "flex", flexWrap: "wrap", gap: spacing.sm }}
              >
                {product.variants.map((v) => {
                  const active = v.id === selectedVariantId;
                  return (
                    <button
                      key={v.id}
                      role="radio"
                      aria-checked={active}
                      onClick={() => setSelectedVariantId(v.id)}
                      style={{
                        padding: "10px 16px",
                        minHeight: 44,
                        background: active ? colors.brandLight : colors.surface,
                        border: `1px solid ${active ? colors.brand : colors.borderStrong}`,
                        color: active ? colors.brand : colors.textPrimary,
                        borderRadius: radius.sm,
                        fontSize: "14px",
                        fontWeight: active ? 600 : 500,
                        cursor: "pointer",
                      }}
                    >
                      {v.title} · ${parseFloat(v.price).toFixed(2)}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <Button
            variant="primary"
            size="lg"
            fullWidth
            disabled={!selectedVariant || soldOut}
            onClick={handleAdd}
            style={{ marginTop: spacing.lg, boxShadow: shadow.sm }}
          >
            {soldOut ? "Sold out" : "Add to Cart"}
          </Button>

          {product.tags.length > 0 && (
            <div style={{ marginTop: spacing.lg, display: "flex", flexWrap: "wrap", gap: 6 }}>
              {product.tags.map((tag) => (
                <span
                  key={tag}
                  style={{
                    fontSize: "12px",
                    background: colors.surfaceMuted,
                    color: colors.textSecondary,
                    padding: "3px 10px",
                    borderRadius: 999,
                  }}
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
