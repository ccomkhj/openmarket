import { useState } from "react";
import { api, type CloseSummary } from "@openmarket/shared";

const DENOMS = ["100", "50", "20", "10", "5", "2", "1", "0.5", "0.2", "0.1"];

export function ShiftClose({ onClosed }: { onClosed: (s: CloseSummary) => void }) {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [summary, setSummary] = useState<CloseSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const total = DENOMS.reduce((s, d) => s + parseFloat(d) * (counts[d] || 0), 0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const s = await api.kassenbuch.close(counts);
      setSummary(s);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (summary) {
    return (
      <div style={{ maxWidth: 400, margin: "32px auto" }}>
        <h1>Shift closed</h1>
        <p>Expected: EUR {summary.expected}</p>
        <p>Counted: EUR {summary.counted}</p>
        <p style={{ color: parseFloat(summary.difference) === 0 ? "green" : "red" }}>
          Difference: EUR {summary.difference}
        </p>
        <button onClick={() => onClosed(summary)}>Done</button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} style={{ maxWidth: 400, margin: "32px auto" }}>
      <h1>Close shift</h1>
      <p>Count closing cash by denomination:</p>
      {DENOMS.map((d) => (
        <div key={d}>
          <label>EUR {d}: </label>
          <input
            type="number" min={0} value={counts[d] ?? 0}
            onChange={(e) => setCounts({ ...counts, [d]: parseInt(e.target.value || "0") })}
          />
        </div>
      ))}
      <p><strong>Total counted: EUR {total.toFixed(2)}</strong></p>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      <button type="submit">Close shift</button>
    </form>
  );
}
