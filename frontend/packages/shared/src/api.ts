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
  },
  variants: {
    lookup: (barcode: string) =>
      request<import("./types").VariantLookup>(`/variants/lookup?barcode=${encodeURIComponent(barcode)}`),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").ProductVariant>(`/variants/${id}`, { method: "PUT", body: JSON.stringify(data) }),
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
};
