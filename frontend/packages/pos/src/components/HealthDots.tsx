import { useEffect, useState } from "react";
import { api } from "@openmarket/shared";

type DotState = "ok" | "fail" | "unknown";

function Dot({ label, state }: { label: string; state: DotState }) {
  const color = state === "ok" ? "#2ecc40" : state === "fail" ? "#ff4136" : "#aaaaaa";
  return (
    <span title={label} style={{ display: "inline-flex", alignItems: "center", gap: 4, marginRight: 12 }}>
      <span style={{ width: 10, height: 10, borderRadius: 5, background: color, display: "inline-block" }} />
      <span style={{ fontSize: 11 }}>{label}</span>
    </span>
  );
}

export function HealthDots() {
  const [db, setDb] = useState<DotState>("unknown");
  const [fk, setFk] = useState<DotState>("unknown");
  const [pr, setPr] = useState<DotState>("unknown");
  const [tm, setTm] = useState<DotState>("unknown");

  useEffect(() => {
    let alive = true;
    async function poll() {
      const probes: Array<[() => Promise<{ online?: boolean; paper_ok?: boolean }>, (s: DotState) => void]> = [
        [api.health.db, setDb],
        [api.health.fiskaly, setFk],
        [api.health.printer, setPr],
        [api.health.terminal, setTm],
      ];
      for (const [fn, set] of probes) {
        try {
          const r = await fn();
          const ok = (r.online ?? true) && (r.paper_ok ?? true);
          if (alive) set(ok ? "ok" : "fail");
        } catch {
          if (alive) set("fail");
        }
      }
    }
    void poll();
    const t = setInterval(poll, 30_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div style={{ display: "inline-flex", padding: "4px 8px" }}>
      <Dot label="DB" state={db} />
      <Dot label="TSE" state={fk} />
      <Dot label="Printer" state={pr} />
      <Dot label="Terminal" state={tm} />
    </div>
  );
}
