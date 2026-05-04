import type { CSSProperties, ReactNode } from "react";
import { colors, radius, spacing } from "../tokens";
import { useEscapeKey } from "../useEscapeKey";

interface Props {
  /** Click on the backdrop closes the shell unless `busy` is true. */
  onClose: () => void;
  busy?: boolean;
  /** Width preset; "md" ≈ 420px, "lg" ≈ 560px. Inline width still wins. */
  width?: "sm" | "md" | "lg";
  /** Anchor: "center" (default) or "top" for command-palette-style overlays. */
  align?: "center" | "top";
  /** Default true: Escape calls `onClose`. Set false when the caller wires its own
   * Escape handler (e.g. nested confirms that need to close the inner layer first). */
  closeOnEscape?: boolean;
  children: ReactNode;
}

const WIDTHS: Record<NonNullable<Props["width"]>, string> = {
  sm: "min(360px, 100%)",
  md: "min(420px, 100%)",
  lg: "min(560px, calc(100vw - 32px))",
};

/** Common modal scaffold: dimmed backdrop, panel, Escape-to-close. Children render
 * inside a padded white panel — supply your own headings, fields, and footer. */
export function ModalShell({
  onClose, busy = false, width = "md", align = "center",
  closeOnEscape = true, children,
}: Props) {
  useEscapeKey(onClose, !busy && closeOnEscape);
  return (
    <div
      onClick={() => { if (!busy) onClose(); }}
      style={{
        ...overlay,
        alignItems: align === "top" ? "flex-start" : "center",
        paddingTop: align === "top" ? "10vh" : spacing.md,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ ...panel, width: WIDTHS[width] }}
      >
        {children}
      </div>
    </div>
  );
}

export const modalLabelStyle: CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 700,
  color: colors.textSecondary,
  textTransform: "uppercase",
  letterSpacing: "0.5px",
  marginBottom: 4,
};

const overlay: CSSProperties = {
  position: "fixed",
  inset: 0,
  zIndex: 1100,
  background: "rgba(15, 15, 20, 0.6)",
  display: "flex",
  justifyContent: "center",
  padding: spacing.md,
};

const panel: CSSProperties = {
  background: colors.surface,
  borderRadius: radius.md,
  padding: spacing.lg,
  boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
};
