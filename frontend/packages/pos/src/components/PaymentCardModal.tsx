import { useEffect, useState } from "react";
import { api, type CardPaymentResult } from "@openmarket/shared";

type Phase = "idle" | "authorizing" | "approved" | "declined" | "error";

export function PaymentCardModal({
  orderId, total, onPaid, onCancel,
}: {
  orderId: number; total: string;
  onPaid: (r: CardPaymentResult) => void;
  onCancel: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setPhase("authorizing"); setError(null);
    try {
      const r = await api.payment.card({
        client_id: crypto.randomUUID(), order_id: orderId,
      });
      setPhase("approved");
      onPaid(r);
    } catch (err) {
      const msg = (err as Error).message;
      if (msg.toLowerCase().includes("declined")) setPhase("declined");
      else setPhase("error");
      setError(msg);
    }
  }

  useEffect(() => { void start(); }, []);

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "white", padding: 24, minWidth: 320 }}>
        <h2>Card payment</h2>
        <p>Total: <strong>EUR {total}</strong></p>
        {phase === "authorizing" && <p>Insert / tap card on terminal...</p>}
        {phase === "approved" && <p style={{ color: "green" }}>Approved</p>}
        {phase === "declined" && (
          <>
            <p style={{ color: "red" }}>Declined. Try again or pay with cash.</p>
            <button onClick={start}>Retry</button>
          </>
        )}
        {phase === "error" && <p style={{ color: "red" }}>Terminal error: {error}</p>}
        <button onClick={onCancel} disabled={phase === "authorizing"}>Cancel</button>
      </div>
    </div>
  );
}
