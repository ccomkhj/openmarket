import { colors, radius } from "../tokens";

const keyframesId = "__om_skeleton_shimmer__";
if (typeof document !== "undefined" && !document.getElementById(keyframesId)) {
  const style = document.createElement("style");
  style.id = keyframesId;
  style.textContent = `
@keyframes om-skeleton-shimmer {
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
}`;
  document.head.appendChild(style);
}

const shimmer: React.CSSProperties = {
  background: `linear-gradient(90deg, ${colors.surfaceMuted} 0px, #ECEEF1 40px, ${colors.surfaceMuted} 80px)`,
  backgroundSize: "200px 100%",
  animation: "om-skeleton-shimmer 1.2s infinite linear",
  borderRadius: radius.sm,
};

export function Skeleton({ width = "100%", height = 14, style }: { width?: number | string; height?: number; style?: React.CSSProperties }) {
  return <div style={{ ...shimmer, width, height, ...style }} />;
}

export function SkeletonRows({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div style={{ padding: 0 }}>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{
          display: "grid",
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gap: 12, padding: "14px 16px",
          borderBottom: `1px solid ${colors.border}`,
        }}>
          {Array.from({ length: columns }).map((__, c) => (
            <Skeleton key={c} height={14} width={c === 0 ? "60%" : "40%"} />
          ))}
        </div>
      ))}
    </div>
  );
}
