import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  baseStyles,
  colors,
  radius,
  shadow,
  spacing,
  useDebounce,
} from "@openmarket/shared";
import type { Customer, OrderListItem, ProductListWithPrice } from "@openmarket/shared";

const SECTIONS = [
  { kind: "product", label: "Products" },
  { kind: "order", label: "Orders" },
  { kind: "customer", label: "Customers" },
] as const;

type ResultKind = (typeof SECTIONS)[number]["kind"];

interface Result {
  kind: ResultKind;
  id: number | string;
  title: string;
  subtitle?: string;
  href: string;
}

const isMacLike =
  typeof navigator !== "undefined" &&
  /(Mac|iPhone|iPad|iPod)/.test(navigator.platform || navigator.userAgent || "");

const SHORTCUT_HINT = isMacLike ? "⌘K" : "Ctrl K";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<ProductListWithPrice[]>([]);
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const debounced = useDebounce(query, 200);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Open with Cmd/Ctrl+K from anywhere; close with Escape. Read `open` via ref so the
  // listener doesn't need to rebind on every state flip.
  const openRef = useRef(open);
  openRef.current = open;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape" && openRef.current) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Reset state every time it reopens.
  useEffect(() => {
    if (open) {
      setQuery("");
      setProducts([]);
      setOrders([]);
      setCustomers([]);
      setActiveIndex(0);
    }
  }, [open]);

  // Run searches in parallel as the user types. AbortController cancels stale work.
  useEffect(() => {
    if (!open) return;
    const term = debounced.trim();
    if (!term) {
      setProducts([]); setOrders([]); setCustomers([]); setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([
      api.products.list({ search: term, limit: 5 }),
      api.orders.list({ search: term, limit: 5 }),
      api.customers.list({ search: term, limit: 5 }),
    ]).then(([p, o, c]) => {
      if (cancelled) return;
      setProducts(p.status === "fulfilled" ? p.value : []);
      setOrders(o.status === "fulfilled" ? o.value : []);
      setCustomers(c.status === "fulfilled" ? c.value : []);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [open, debounced]);

  // Flat result list with a stable absolute index per row.
  const results = useMemo<Result[]>(() => {
    const out: Result[] = [];
    products.forEach((p) => out.push({
      kind: "product",
      id: p.id,
      title: p.title,
      subtitle: p.product_type || undefined,
      href: `/products?q=${encodeURIComponent(p.title)}`,
    }));
    orders.forEach((o) => out.push({
      kind: "order",
      id: o.id,
      title: o.order_number,
      subtitle: [o.customer_name, `$${o.total_price}`, o.fulfillment_status]
        .filter(Boolean).join(" · "),
      href: `/orders?q=${encodeURIComponent(o.order_number)}`,
    }));
    customers.forEach((c) => {
      const name = `${c.first_name ?? ""} ${c.last_name ?? ""}`.trim();
      const display = name || c.phone || c.email || `Customer #${c.id}`;
      // Receiving page searches across name/email/phone; sending the displayed name
      // (when available) makes the link self-consistent — click "Jane Doe" → search "Jane Doe".
      const q = name || c.phone || c.email || "";
      out.push({
        kind: "customer",
        id: c.id,
        title: display,
        subtitle: [c.phone, c.email].filter(Boolean).join(" · ") || undefined,
        href: `/customers${q ? `?q=${encodeURIComponent(q)}` : ""}`,
      });
    });
    return out;
  }, [products, orders, customers]);

  // Clamp activeIndex when result count changes (results shrink under the cursor).
  useEffect(() => {
    setActiveIndex((i) => {
      if (results.length === 0) return 0;
      return Math.min(Math.max(i, 0), results.length - 1);
    });
  }, [results.length]);

  const go = (r: Result) => {
    setOpen(false);
    navigate(r.href);
  };

  const onPaletteKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(results.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const r = results[activeIndex];
      if (r) go(r);
    }
  };


  // Tiny focus trap: keep Tab inside the panel while open.
  const onTrapKey = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !open) return;
    const root = panelRef.current;
    if (!root) return;
    const focusable = root.querySelectorAll<HTMLElement>(
      'input, button, [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  };

  const panelRef = useRef<HTMLDivElement | null>(null);

  if (!open) return null;

  const renderSection = ({ kind, label }: typeof SECTIONS[number]) => {
    // Walk the flat results once per section, keeping the absolute index for each row.
    const items = results
      .map((r, index) => ({ r, index }))
      .filter(({ r }) => r.kind === kind);
    if (items.length === 0) return null;
    return (
      <div key={kind} role="group" aria-labelledby={`cp-section-${kind}`}>
        <div
          id={`cp-section-${kind}`}
          style={{
            fontSize: 11, fontWeight: 700, color: colors.textSecondary,
            textTransform: "uppercase", letterSpacing: "0.5px",
            padding: `${spacing.sm} ${spacing.md} 4px`,
          }}
        >
          {label}
        </div>
        {items.map(({ r, index }) => {
          const active = index === activeIndex;
          return (
            <button
              key={`${r.kind}:${r.id}`}
              id={`cp-row-${index}`}
              role="option"
              aria-selected={active}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => go(r)}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: `${spacing.sm} ${spacing.md}`,
                background: active ? colors.brandLight : "transparent",
                border: "none", cursor: "pointer",
                color: colors.textPrimary, fontFamily: "inherit",
              }}
            >
              <div style={{
                fontSize: 14, fontWeight: 600,
                color: active ? colors.brand : colors.textPrimary,
              }}>
                {r.title}
              </div>
              {r.subtitle && (
                <div style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>
                  {r.subtitle}
                </div>
              )}
            </button>
          );
        })}
      </div>
    );
  };

  const activeRowId = results[activeIndex] ? `cp-row-${activeIndex}` : undefined;

  return (
    <div
      onClick={() => setOpen(false)}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(15, 15, 20, 0.5)",
        display: "flex", alignItems: "flex-start", justifyContent: "center",
        paddingTop: "12vh",
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Search products, orders, and customers"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => { onPaletteKey(e); onTrapKey(e); }}
        style={{
          width: "min(640px, calc(100vw - 32px))",
          background: colors.surface,
          borderRadius: radius.md,
          boxShadow: shadow.lg,
          border: `1px solid ${colors.border}`,
          overflow: "hidden",
        }}
      >
        <input
          ref={inputRef}
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search products, orders, customers…"
          role="combobox"
          aria-expanded
          aria-controls="cp-listbox"
          aria-activedescendant={activeRowId}
          aria-autocomplete="list"
          style={{
            ...baseStyles.input,
            border: "none",
            borderBottom: `1px solid ${colors.border}`,
            borderRadius: 0,
            fontSize: "16px",
            padding: `${spacing.md} ${spacing.lg}`,
          }}
        />
        <div
          id="cp-listbox"
          role="listbox"
          aria-label="Search results"
          style={{ maxHeight: "60vh", overflowY: "auto", padding: "4px 0" }}
        >
          {!debounced.trim() && (
            <div style={{ padding: spacing.lg, color: colors.textSecondary, fontSize: 13 }}>
              Start typing to search across products, orders, and customers.
              <div style={{ marginTop: spacing.sm, fontSize: 12 }}>
                <kbd style={kbdStyle}>↑</kbd> <kbd style={kbdStyle}>↓</kbd> to navigate ·{" "}
                <kbd style={kbdStyle}>Enter</kbd> to open ·{" "}
                <kbd style={kbdStyle}>Esc</kbd> to close
              </div>
            </div>
          )}
          {debounced.trim() && loading && (
            <div style={{ padding: spacing.lg, color: colors.textSecondary, fontSize: 13 }}>
              Searching…
            </div>
          )}
          {debounced.trim() && !loading && results.length === 0 && (
            <div style={{ padding: spacing.lg, color: colors.textSecondary, fontSize: 13 }}>
              No results for “{debounced}”.
            </div>
          )}
          {SECTIONS.map(renderSection)}
        </div>
      </div>
    </div>
  );
}

export const COMMAND_PALETTE_HINT = SHORTCUT_HINT;

const kbdStyle: React.CSSProperties = {
  background: "#EDEDF0",
  color: colors.textSecondary,
  border: `1px solid ${colors.border}`,
  borderRadius: 4,
  padding: "1px 6px",
  fontSize: 11,
  fontFamily: "monospace",
};
