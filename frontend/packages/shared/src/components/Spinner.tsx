import { colors } from "../tokens";

export function Spinner({ size = 24, label }: { size?: number; label?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px", padding: "40px 0" }}>
      <div
        style={{
          width: size, height: size,
          border: `3px solid ${colors.border}`,
          borderTopColor: colors.brand,
          borderRadius: "50%",
          animation: "spin 0.6s linear infinite",
        }}
      />
      {label && <span style={{ color: colors.textSecondary, fontSize: "14px" }}>{label}</span>}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
