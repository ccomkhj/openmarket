import type { CSSProperties, ButtonHTMLAttributes } from "react";
import { colors, radius, font } from "../tokens";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md" | "lg";
  fullWidth?: boolean;
  loading?: boolean;
}

const variantStyles: Record<ButtonVariant, CSSProperties> = {
  primary: { background: colors.brand, color: "#FFFFFF", border: "none" },
  secondary: { background: colors.surfaceMuted, color: colors.textPrimary, border: `1px solid ${colors.borderStrong}` },
  danger: { background: colors.dangerSurface, color: colors.danger, border: `1px solid ${colors.danger}` },
  ghost: { background: "transparent", color: colors.textSecondary, border: "1px solid transparent" },
};

const sizeStyles: Record<string, CSSProperties> = {
  sm: { padding: "4px 10px", fontSize: "13px" },
  md: { padding: "7px 14px", fontSize: "14px" },
  lg: { padding: "10px 20px", fontSize: "15px" },
};

export function Button({
  variant = "secondary", size = "md", fullWidth = false, loading = false,
  disabled, style, children, ...props
}: ButtonProps) {
  const baseStyle: CSSProperties = {
    borderRadius: radius.sm, fontFamily: font.body, fontWeight: 500,
    cursor: disabled || loading ? "not-allowed" : "pointer",
    opacity: disabled || loading ? 0.6 : 1,
    transition: "all 0.15s ease",
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "6px",
    width: fullWidth ? "100%" : undefined,
    ...variantStyles[variant], ...sizeStyles[size], ...style,
  };
  return (
    <button style={baseStyle} disabled={disabled || loading} {...props}>
      {loading ? "..." : children}
    </button>
  );
}
