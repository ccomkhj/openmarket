import { useState } from "react";
import { api } from "@openmarket/shared";

export function DsfinvkExport() {
  const today = new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);

  return (
    <div style={{ maxWidth: 600, margin: "32px auto" }}>
      <h1>DSFinV-K Export</h1>
      <p>Generates a ZIP for the date range, ready to hand to the Steuerberater.</p>
      <label>From: <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
      <label> To: <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      <p>
        <a
          href={api.reports.dsfinvkUrl(from, to)}
          download={`dsfinvk-${from}-${to}.zip`}
        >
          <button>Download ZIP</button>
        </a>
      </p>
    </div>
  );
}
