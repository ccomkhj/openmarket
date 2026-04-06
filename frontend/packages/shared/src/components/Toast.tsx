import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { colors, radius, spacing, shadow, font } from "../tokens";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

const nextId = { current: 0 };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: ToastType = "success") => {
    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      <div style={{ position: "fixed", bottom: spacing.lg, right: spacing.lg, zIndex: 9999, display: "flex", flexDirection: "column", gap: spacing.sm }}>
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDone={() => removeToast(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDone }: { toast: Toast; onDone: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDone, 3000);
    return () => clearTimeout(timer);
  }, [onDone]);

  const bg = toast.type === "success" ? colors.successSurface
    : toast.type === "error" ? colors.dangerSurface
    : colors.surface;
  const fg = toast.type === "success" ? colors.success
    : toast.type === "error" ? colors.danger
    : colors.textPrimary;

  return (
    <div style={{
      background: bg, color: fg, border: `1px solid ${fg}`,
      padding: "10px 16px", borderRadius: radius.sm,
      fontSize: "14px", fontFamily: font.body, fontWeight: 500,
      boxShadow: shadow.md, minWidth: 240, maxWidth: 400,
      cursor: "pointer",
    }} onClick={onDone}>
      {toast.message}
    </div>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
