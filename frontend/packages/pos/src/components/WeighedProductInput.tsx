import { useState } from "react";
import { Button, colors, radius, spacing } from "@openmarket/shared";

type Props = {
  title: string;
  pricePerKg: string;
  weightUnit?: "kg" | "g" | "100g" | null;
  minKg?: string | null;
  maxKg?: string | null;
  onConfirm: (quantityKg: number) => void;
  onCancel: () => void;
};

export function WeighedProductInput({
  title,
  pricePerKg,
  weightUnit,
  minKg,
  maxKg,
  onConfirm,
  onCancel,
}: Props) {
  const [buffer, setBuffer] = useState("");

  const qty = buffer ? parseFloat(buffer) : 0;
  const pricePerKgNum = parseFloat(pricePerKg) || 0;
  const total = qty * pricePerKgNum;

  const minNum = minKg ? parseFloat(minKg) : null;
  const maxNum = maxKg ? parseFloat(maxKg) : null;

  let validationError = "";
  if (qty > 0) {
    if (minNum != null && qty < minNum) {
      validationError = `Minimum weight is ${minNum} kg`;
    } else if (maxNum != null && qty > maxNum) {
      validationError = `Maximum weight is ${maxNum} kg`;
    }
  }

  function press(ch: string) {
    if (ch === "." && buffer.includes(".")) return;
    if (buffer.length >= 6) return;
    setBuffer(buffer + ch);
  }

  function back() {
    setBuffer(buffer.slice(0, -1));
  }

  function confirm() {
    if (!qty) return;
    if (minNum != null && qty < minNum) return;
    if (maxNum != null && qty > maxNum) return;
    onConfirm(qty);
  }

  const canConfirm = qty > 0 && !validationError;

  const keypadButton = {
    padding: "20px",
    fontSize: "24px",
    fontWeight: 600,
    background: colors.surface,
    border: `1px solid ${colors.borderStrong}`,
    borderRadius: radius.sm,
    cursor: "pointer",
  } as const;

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          background: colors.surface,
          borderRadius: radius.md,
          padding: spacing.lg,
          minWidth: 360,
          maxWidth: 440,
          boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
        }}
      >
        <h2 style={{ margin: 0, marginBottom: spacing.sm }}>{title}</h2>
        <p style={{ fontSize: 20, margin: 0, color: colors.textSecondary }}>
          {pricePerKg} {"\u20ac"}/kg
          {weightUnit && weightUnit !== "kg" ? ` (priced per ${weightUnit})` : ""}
        </p>

        <div
          style={{
            marginTop: spacing.md,
            padding: spacing.md,
            background: colors.surfaceMuted,
            borderRadius: radius.sm,
            textAlign: "right",
          }}
        >
          <div style={{ fontSize: 56, fontFamily: "monospace", fontWeight: 600 }}>
            {buffer || "0"} <small style={{ fontSize: 24, fontWeight: 400 }}>kg</small>
          </div>
          <div style={{ fontSize: 28, fontWeight: 600, color: colors.brand }}>
            {total.toFixed(2)} {"\u20ac"}
          </div>
        </div>

        {(minNum != null || maxNum != null) && (
          <p style={{ fontSize: 13, color: colors.textSecondary, margin: `${spacing.sm} 0 0` }}>
            Allowed range:
            {minNum != null ? ` min ${minNum} kg` : ""}
            {minNum != null && maxNum != null ? "," : ""}
            {maxNum != null ? ` max ${maxNum} kg` : ""}
          </p>
        )}

        {validationError && (
          <div
            style={{
              background: colors.dangerSurface,
              color: colors.danger,
              padding: "8px 12px",
              borderRadius: radius.sm,
              fontSize: 14,
              marginTop: spacing.sm,
            }}
          >
            {validationError}
          </div>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: spacing.sm,
            marginTop: spacing.md,
          }}
        >
          {"123456789".split("").map((d) => (
            <button key={d} style={keypadButton} onClick={() => press(d)} type="button">
              {d}
            </button>
          ))}
          <button style={keypadButton} onClick={() => press(".")} type="button">
            .
          </button>
          <button style={keypadButton} onClick={() => press("0")} type="button">
            0
          </button>
          <button style={keypadButton} onClick={back} type="button" aria-label="Backspace">
            {"\u2190"}
          </button>
        </div>

        <div
          style={{
            display: "flex",
            gap: spacing.sm,
            marginTop: spacing.lg,
            justifyContent: "flex-end",
          }}
        >
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!canConfirm} onClick={confirm}>
            Add
          </Button>
        </div>
      </div>
    </div>
  );
}
