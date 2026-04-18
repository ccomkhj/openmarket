import { useEffect, useState } from "react";
import { posLogin } from "@openmarket/shared";

type Cashier = { user_id: number; full_name: string };

export function CashierLogin({ onSuccess }: { onSuccess: () => void }) {
  const [cashiers, setCashiers] = useState<Cashier[]>([]);
  const [selected, setSelected] = useState<Cashier | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/auth/cashiers", { credentials: "include" })
      .then((r) => r.json())
      .then(setCashiers)
      .catch(() => setError("Could not load cashier list"));
  }, []);

  async function submit() {
    if (!selected) return;
    setError(null);
    try {
      await posLogin(selected.user_id, pin);
      onSuccess();
    } catch (err) {
      setError((err as Error).message);
      setPin("");
    }
  }

  function press(digit: string) {
    if (pin.length >= 6) return;
    setPin(pin + digit);
  }

  if (!selected) {
    return (
      <div style={{ padding: 32 }}>
        <h1>Select cashier</h1>
        <ul>
          {cashiers.map((c) => (
            <li key={c.user_id}>
              <button onClick={() => setSelected(c)}>{c.full_name}</button>
            </li>
          ))}
        </ul>
        {error && <p role="alert">{error}</p>}
      </div>
    );
  }

  return (
    <div style={{ padding: 32, textAlign: "center" }}>
      <h1>{selected.full_name}</h1>
      <p>Enter PIN</p>
      <div style={{ fontSize: 48, letterSpacing: 16 }}>{"\u2022".repeat(pin.length)}</div>
      {error && <p role="alert">{error}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 80px)", gap: 8, justifyContent: "center" }}>
        {"123456789".split("").map((d) => (
          <button key={d} onClick={() => press(d)} style={{ height: 80, fontSize: 32 }}>{d}</button>
        ))}
        <button onClick={() => setPin("")} style={{ height: 80 }}>clr</button>
        <button onClick={() => press("0")} style={{ height: 80, fontSize: 32 }}>0</button>
        <button onClick={submit} style={{ height: 80 }}>{"\u21B5"}</button>
      </div>
      <button onClick={() => { setSelected(null); setPin(""); }}>{"\u2190"} different cashier</button>
    </div>
  );
}
