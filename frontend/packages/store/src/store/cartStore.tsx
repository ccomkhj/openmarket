import { createContext, useContext, useState, ReactNode, useCallback, useEffect } from "react";
import type { CartItem, Product, ProductVariant } from "@openmarket/shared";

const CART_KEY = "openmarket_cart";

function loadCart(): CartItem[] {
  try {
    const raw = localStorage.getItem(CART_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveCart(items: CartItem[]) {
  try {
    localStorage.setItem(CART_KEY, JSON.stringify(items));
  } catch { /* quota exceeded - silently ignore */ }
}

interface CartContextType {
  items: CartItem[];
  addItem: (product: Product, variant: ProductVariant) => void;
  removeItem: (variantId: number) => void;
  updateQuantity: (variantId: number, quantity: number) => void;
  clearCart: () => void;
  total: number;
}

const CartContext = createContext<CartContextType | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(loadCart);

  useEffect(() => { saveCart(items); }, [items]);

  const addItem = useCallback((product: Product, variant: ProductVariant) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.variant.id === variant.id);
      if (existing) {
        return prev.map((i) => i.variant.id === variant.id ? { ...i, quantity: i.quantity + 1 } : i);
      }
      return [...prev, { product, variant, quantity: 1 }];
    });
  }, []);

  const removeItem = useCallback((variantId: number) => {
    setItems((prev) => prev.filter((i) => i.variant.id !== variantId));
  }, []);

  const updateQuantity = useCallback((variantId: number, quantity: number) => {
    if (quantity <= 0) { setItems((prev) => prev.filter((i) => i.variant.id !== variantId)); return; }
    setItems((prev) => prev.map((i) => (i.variant.id === variantId ? { ...i, quantity } : i)));
  }, []);

  const clearCart = useCallback(() => setItems([]), []);

  const total = items.reduce((sum, item) => sum + parseFloat(item.variant.price) * item.quantity, 0);

  return (
    <CartContext.Provider value={{ items, addItem, removeItem, updateQuantity, clearCart, total }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}
