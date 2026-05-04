import { colors, radius, spacing, shadow, font } from "../tokens";
import { Button } from "./Button";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary";
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title, message, confirmLabel = "Confirm", cancelLabel = "Cancel",
  variant = "primary", loading = false, onConfirm, onCancel,
}: ConfirmDialogProps) {
  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 10000, fontFamily: font.body,
      }}
      onClick={(e) => { if (e.target === e.currentTarget && !loading) onCancel(); }}
    >
      <div style={{
        background: colors.surface, borderRadius: radius.md,
        padding: spacing.lg, width: 380, boxShadow: shadow.lg,
      }}>
        <h3 style={{ margin: "0 0 8px", fontSize: "16px" }}>{title}</h3>
        <p style={{ color: colors.textSecondary, fontSize: "14px", margin: "0 0 20px" }}>{message}</p>
        <div style={{ display: "flex", gap: spacing.sm, justifyContent: "flex-end" }}>
          <Button variant="ghost" onClick={onCancel} disabled={loading}>{cancelLabel}</Button>
          <Button variant={variant} onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  );
}
