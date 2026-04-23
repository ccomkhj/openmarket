import { useState } from "react";
import { api, type ZReport as ZReportT } from "@openmarket/shared";

export function ZReport() {
  const today = new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState(`${today}T00:00:00`);
  const [to, setTo] = useState(`${today}T23:59:59`);
  const [report, setReport] = useState<ZReportT | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try { setReport(await api.reports.zReport(from, to)); }
    catch (e) { setError((e as Error).message); }
  }

  return (
    <div style={{ maxWidth: 800, margin: "32px auto" }}>
      <h1>Z-Report</h1>
      <label>From: <input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
      <label> To: <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      <button onClick={load}>Run</button>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      {report && (
        <pre style={{ background: "#f4f4f4", padding: 12 }}>{JSON.stringify(report, null, 2)}</pre>
      )}
    </div>
  );
}
