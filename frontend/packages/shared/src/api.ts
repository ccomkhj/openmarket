import type { CashPaymentResult, CardPaymentResult, CloseSummary, HealthStatus, KassenbuchEntry, ZReport, VariantDetail, PosTransactionListItem } from "./types";

const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function qs(params: Record<string, unknown>): string {
  const entries = Object.entries(params).filter(([, v]) => v != null && v !== "");
  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

export const api = {
  products: {
    list: (params?: { status?: string; search?: string; product_type?: string; sort_by?: string; limit?: number; offset?: number }) =>
      request<import("./types").ProductListWithPrice[]>(`/products${qs(params ?? {})}`),
    get: (id: number) => request<import("./types").Product>(`/products/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Product>("/products", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Product>(`/products/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    archive: (id: number) =>
      request<import("./types").Product>(`/products/${id}`, { method: "DELETE" }),
    uploadImage: async (productId: number, file: Blob, filename?: string) => {
      const form = new FormData();
      form.append("file", file, filename || "photo.jpg");
      const response = await fetch(`${API_BASE}/products/${productId}/images`, { method: "POST", body: form });
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }
      return response.json() as Promise<import("./types").ProductImage>;
    },
    importCsv: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${API_BASE}/products/import-csv`, {
        method: "POST", credentials: "include", body: fd,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return (await res.json()) as { created: number; skipped: number; errors: string[] };
    },
  },
  variants: {
    lookup: (barcode: string) =>
      request<VariantDetail>(`/variants/lookup?barcode=${encodeURIComponent(barcode)}`),
    update: (id: number, data: Partial<Omit<VariantDetail, "id" | "product_id">>) =>
      request<VariantDetail>(`/variants/${id}`, {
        method: "PUT", body: JSON.stringify(data),
      }),
  },
  collections: {
    list: () => request<import("./types").Collection[]>("/collections"),
    products: (id: number) =>
      request<import("./types").ProductListWithPrice[]>(`/collections/${id}/products`),
  },
  inventory: {
    levels: (locationId: number) =>
      request<import("./types").InventoryLevel[]>(`/inventory-levels?location_id=${locationId}`),
    set: (data: { inventory_item_id: number; location_id: number; available: number }) =>
      request<import("./types").InventoryLevel>("/inventory-levels/set", { method: "POST", body: JSON.stringify(data) }),
    adjust: (data: { inventory_item_id: number; location_id: number; available_adjustment: number }) =>
      request<import("./types").InventoryLevel>("/inventory-levels/adjust", { method: "POST", body: JSON.stringify(data) }),
    lowStockCount: (locationId: number) =>
      request<{ count: number }>(`/inventory-levels/low-stock-count?location_id=${locationId}`),
  },
  locations: {
    list: () => request<import("./types").Location[]>("/locations"),
  },
  orders: {
    list: (params?: { source?: string; fulfillment_status?: string; search?: string; date_from?: string; date_to?: string; limit?: number; offset?: number }) =>
      request<import("./types").OrderListItem[]>(`/orders${qs(params ?? {})}`),
    get: (id: number) => request<import("./types").Order>(`/orders/${id}`),
    lookup: (orderNumber: string) =>
      request<import("./types").Order>(`/orders/lookup?order_number=${encodeURIComponent(orderNumber)}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Order>("/orders", { method: "POST", body: JSON.stringify(data) }),
  },
  fulfillments: {
    create: (orderId: number, data: { status: string }) =>
      request<import("./types").Fulfillment>(`/orders/${orderId}/fulfillments`, { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: { status: string }) =>
      request<import("./types").Fulfillment>(`/fulfillments/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  },
  discounts: {
    lookup: (code: string) =>
      request<import("./types").Discount>(`/discounts/lookup?code=${encodeURIComponent(code)}`, { method: "POST" }),
    list: () => request<import("./types").Discount[]>("/discounts"),
    create: (data: import("./types").DiscountCreate) =>
      request<import("./types").Discount>("/discounts", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Discount>(`/discounts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: number) => request<{ ok: boolean }>(`/discounts/${id}`, { method: "DELETE" }),
  },
  analytics: {
    summary: (days?: number) =>
      request<import("./types").AnalyticsSummary>(`/analytics/summary${days ? `?days=${days}` : ""}`),
  },
  taxRates: {
    list: () => request<import("./types").TaxRate[]>("/tax-rates"),
    create: (data: Record<string, unknown>) =>
      request<import("./types").TaxRate>("/tax-rates", { method: "POST", body: JSON.stringify(data) }),
  },
  shippingMethods: {
    list: () => request<import("./types").ShippingMethod[]>("/shipping-methods"),
    create: (data: Record<string, unknown>) =>
      request<import("./types").ShippingMethod>("/shipping-methods", { method: "POST", body: JSON.stringify(data) }),
  },
  customers: {
    list: (params?: { search?: string; limit?: number; offset?: number }) =>
      request<import("./types").Customer[]>(`/customers${qs(params ?? {})}`),
    get: (id: number) => request<import("./types").Customer>(`/customers/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Customer>("/customers", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Customer>(`/customers/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    lookup: (params: { email?: string; phone?: string }) =>
      request<import("./types").Customer>(`/customers/lookup${qs(params)}`),
    orders: (id: number) =>
      request<import("./types").OrderListItem[]>(`/customers/${id}/orders`),
  },
  users: {
    list: () => request<Array<{
      id: number;
      email: string | null;
      full_name: string;
      role: "owner" | "manager" | "cashier";
      active: boolean;
      created_at: string | null;
      last_login_at: string | null;
    }>>("/users"),
    create: (data: {
      email?: string | null;
      password?: string | null;
      pin?: string | null;
      full_name: string;
      role: "owner" | "manager" | "cashier";
    }) => request<{
      id: number; email: string | null; full_name: string; role: string; active: boolean;
    }>("/users", { method: "POST", body: JSON.stringify(data) }),
    deactivate: (id: number) => request<{ id: number; active: boolean }>(
      `/users/${id}/deactivate`,
      { method: "PATCH" },
    ),
  },
  payment: {
    cash: (data: { client_id: string; order_id: number; tendered: string }) =>
      request<CashPaymentResult>("/payment/cash", { method: "POST", body: JSON.stringify(data) }),
    card: (data: { client_id: string; order_id: number }) =>
      request<CardPaymentResult>("/payment/card", { method: "POST", body: JSON.stringify(data) }),
  },
  receipts: {
    reprint: (posTransactionId: string) =>
      request<{ id: number; pos_transaction_id: string; status: string; attempts: number; last_error: string | null; printed_at: string | null }>(
        `/receipts/${posTransactionId}/reprint`,
        { method: "POST" },
      ),
  },
  kassenbuch: {
    open: (denominations: Record<string, number>) =>
      request<KassenbuchEntry>("/kassenbuch/open", { method: "POST", body: JSON.stringify({ denominations }) }),
    close: (denominations: Record<string, number>) =>
      request<CloseSummary>("/kassenbuch/close", { method: "POST", body: JSON.stringify({ denominations }) }),
    paidIn: (amount: string, reason: string) =>
      request<KassenbuchEntry>("/kassenbuch/paid-in", { method: "POST", body: JSON.stringify({ amount, reason }) }),
    paidOut: (amount: string, reason: string) =>
      request<KassenbuchEntry>("/kassenbuch/paid-out", { method: "POST", body: JSON.stringify({ amount, reason }) }),
    status: () => request<{ open: boolean }>("/kassenbuch/status"),
  },
  reports: {
    zReport: (date_from: string, date_to: string) =>
      request<ZReport>(`/reports/z-report?date_from=${encodeURIComponent(date_from)}&date_to=${encodeURIComponent(date_to)}`),
    dsfinvkUrl: (date_from: string, date_to: string) =>
      `/api/reports/dsfinvk?date_from=${date_from}&date_to=${date_to}`,
  },
  posTransactions: {
    list: (opts?: { limit?: number; offset?: number }) => {
      const p = new URLSearchParams();
      if (opts?.limit != null) p.set("limit", String(opts.limit));
      if (opts?.offset != null) p.set("offset", String(opts.offset));
      const qs = p.toString();
      return request<{ items: PosTransactionListItem[]; limit: number; offset: number }>(
        `/pos-transactions${qs ? "?" + qs : ""}`,
      );
    },
  },
  storno: {
    void: (txId: string) =>
      request<{ id: string; voids_transaction_id: string; tse_signature: string; receipt_number: number }>(
        `/pos-transactions/${txId}/void`, { method: "POST" }
      ),
  },
  health: {
    db: () => request<HealthStatus>("/health"),
    fiskaly: () => request<HealthStatus>("/health/fiskaly"),
    printer: () => request<HealthStatus>("/health/printer"),
    terminal: () => request<HealthStatus>("/health/terminal"),
  },
};
