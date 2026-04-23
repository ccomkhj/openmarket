import { useState } from "react";
import { api } from "@openmarket/shared";

const DENOMS = ["100", "50", "20", "10", "5", "2", "1", "0.5", "0.2", "0.1"];

export function ShiftOpen({ onOpened }: { onOpened: () => void }) {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const total = DENOMS.reduce((s, d) => s + parseFloat(d) * (counts[d] || 0), 0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.kassenbuch.open(counts);
      onOpened();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} style={{ maxWidth: 400, margin: "32px auto" }}>
      <h1>Open shift</h1>
      <p>Count opening cash by denomination:</p>
      {DENOMS.map((d) => (
        <div key={d}>
          <label>EUR {d}: </label>
          <input
            type="number" min={0} value={counts[d] ?? 0}
            onChange={(e) => setCounts({ ...counts, [d]: parseInt(e.target.value || "0") })}
          />
        </div>
      ))}
      <p><strong>Total: EUR {total.toFixed(2)}</strong></p>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      <button type="submit">Open shift</button>
    </form>
  );
}
