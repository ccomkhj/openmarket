const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export const api = {
  products: {
    list: (params?: { status?: string; search?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string>).toString();
      return request<import("./types").ProductListItem[]>(`/products${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => request<import("./types").Product>(`/products/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Product>("/products", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Product>(`/products/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    archive: (id: number) =>
      request<import("./types").Product>(`/products/${id}`, { method: "DELETE" }),
  },
  collections: {
    list: () => request<import("./types").Collection[]>("/collections"),
    products: (id: number) =>
      request<import("./types").ProductListItem[]>(`/collections/${id}/products`),
  },
  inventory: {
    levels: (locationId: number) =>
      request<import("./types").InventoryLevel[]>(`/inventory-levels?location_id=${locationId}`),
    set: (data: { inventory_item_id: number; location_id: number; available: number }) =>
      request<import("./types").InventoryLevel>("/inventory-levels/set", { method: "POST", body: JSON.stringify(data) }),
    adjust: (data: { inventory_item_id: number; location_id: number; available_adjustment: number }) =>
      request<import("./types").InventoryLevel>("/inventory-levels/adjust", { method: "POST", body: JSON.stringify(data) }),
  },
  orders: {
    list: (params?: { source?: string; fulfillment_status?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string>).toString();
      return request<import("./types").OrderListItem[]>(`/orders${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => request<import("./types").Order>(`/orders/${id}`),
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
  },
  customers: {
    list: () => request<import("./types").Customer[]>("/customers"),
    get: (id: number) => request<import("./types").Customer>(`/customers/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Customer>("/customers", { method: "POST", body: JSON.stringify(data) }),
  },
};
