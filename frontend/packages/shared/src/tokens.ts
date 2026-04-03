import type { CSSProperties } from "react";

export const colors = {
  brand: "#5B47E0",
  brandHover: "#4A38C9",
  brandLight: "#EDE9FC",
  surface: "#FFFFFF",
  surfaceMuted: "#F7F7F8",
  border: "#E5E5E7",
  borderStrong: "#C7C7CC",
  textPrimary: "#1A1A1A",
  textSecondary: "#6B6B6B",
  textDisabled: "#ADADAD",
  danger: "#D93025",
  dangerSurface: "#FEF2F2",
  success: "#1A7F37",
  successSurface: "#F0FFF4",
  warning: "#B45309",
  warningSurface: "#FFFBEB",
};

export const spacing = {
  xs: "4px",
  sm: "8px",
  md: "16px",
  lg: "24px",
  xl: "40px",
};

export const radius = {
  sm: "6px",
  md: "10px",
  lg: "16px",
};

export const font = {
  body: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif",
  mono: "'SF Mono', 'Fira Code', monospace",
};

export const shadow = {
  sm: "0 1px 2px rgba(0,0,0,0.05)",
  md: "0 2px 8px rgba(0,0,0,0.08)",
  lg: "0 4px 16px rgba(0,0,0,0.12)",
};

export const navHeight = "56px";

export const baseStyles: Record<string, CSSProperties> = {
  page: {
    fontFamily: font.body,
    color: colors.textPrimary,
    minHeight: "100vh",
    background: colors.surfaceMuted,
  },
  nav: {
    padding: `0 ${spacing.lg}`,
    height: navHeight,
    borderBottom: `1px solid ${colors.border}`,
    display: "flex",
    gap: spacing.lg,
    alignItems: "center",
    background: colors.surface,
    position: "sticky" as const,
    top: 0,
    zIndex: 100,
    fontFamily: font.body,
  },
  navBrand: {
    fontWeight: 700,
    fontSize: "1.1rem",
    textDecoration: "none",
    color: colors.brand,
  },
  navLink: {
    textDecoration: "none",
    color: colors.textSecondary,
    fontSize: "0.9rem",
    fontWeight: 500,
  },
  card: {
    background: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: radius.md,
    padding: spacing.lg,
  },
  input: {
    padding: "8px 12px",
    border: `1px solid ${colors.borderStrong}`,
    borderRadius: radius.sm,
    fontSize: "14px",
    fontFamily: font.body,
    outline: "none",
    width: "100%",
    boxSizing: "border-box" as const,
  },
  container: {
    maxWidth: 1200,
    margin: "0 auto",
    padding: spacing.lg,
  },
};
