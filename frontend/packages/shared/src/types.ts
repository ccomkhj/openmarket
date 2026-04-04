export interface ProductVariant {
  id: number;
  product_id: number;
  title: string;
  sku: string;
  barcode: string;
  price: string;
  compare_at_price: string | null;
  position: number;
}

export interface ProductImage {
  id: number;
  src: string;
  position: number;
}

export interface Product {
  id: number;
  title: string;
  handle: string;
  description: string;
  product_type: string;
  status: string;
  tags: string[];
  variants: ProductVariant[];
  images: ProductImage[];
}

export interface ProductListItem {
  id: number;
  title: string;
  handle: string;
  product_type: string;
  status: string;
  tags: string[];
}

export interface Collection {
  id: number;
  title: string;
  handle: string;
  collection_type: string;
  rules: Record<string, unknown> | null;
}

export interface InventoryLevel {
  id: number;
  inventory_item_id: number;
  location_id: number;
  available: number;
  low_stock_threshold: number;
}

export interface Customer {
  id: number;
  email: string | null;
  first_name: string;
  last_name: string;
  phone: string;
  addresses: CustomerAddress[];
}

export interface CustomerAddress {
  id: number;
  address1: string;
  city: string;
  zip: string;
  is_default: boolean;
}

export interface LineItem {
  id: number;
  variant_id: number;
  title: string;
  quantity: number;
  price: string;
}

export interface Order {
  id: number;
  order_number: string;
  customer_id: number | null;
  source: string;
  fulfillment_status: string;
  total_price: string;
  shipping_address: Record<string, string> | null;
  created_at: string;
  line_items: LineItem[];
}

export interface OrderListItem {
  id: number;
  order_number: string;
  source: string;
  fulfillment_status: string;
  total_price: string;
  created_at: string;
}

export interface Fulfillment {
  id: number;
  order_id: number;
  status: string;
  created_at: string;
}

export interface Discount {
  id: number;
  code: string;
  discount_type: string;
  value: string;
  starts_at: string;
  ends_at: string;
}

export interface CartItem {
  variant: ProductVariant;
  product: Product;
  quantity: number;
}

export interface ProductListWithPrice {
  id: number;
  title: string;
  handle: string;
  product_type: string;
  status: string;
  tags: string[];
  min_price: string | null;
  image_url: string | null;
}

export interface VariantLookup {
  id: number;
  product_id: number;
  product_title: string;
  title: string;
  sku: string;
  barcode: string;
  price: string;
  compare_at_price: string | null;
}

export interface DailySales {
  date: string;
  order_count: number;
  revenue: string;
}

export interface TopProduct {
  title: string;
  quantity_sold: number;
  revenue: string;
}

export interface AnalyticsSummary {
  total_revenue: string;
  total_orders: number;
  average_order_value: string;
  daily_sales: DailySales[];
  top_products: TopProduct[];
  orders_by_source: Record<string, number>;
}
