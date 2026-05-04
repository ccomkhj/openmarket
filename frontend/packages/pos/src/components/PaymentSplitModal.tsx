import { useMemo, useState } from "react";
import { api, Button, ModalShell, baseStyles, colors, modalLabelStyle, radius, spacing, useToast } from "@openmarket/shared";

interface Props {
  orderId: number;
  total: string;
  onPaid: (result: { transactionId: string; cashAmount: string; cardAmount: string }) => void;
  onCancel: () => void;
}

const QUICK_TENDERS = [10, 20, 50, 100];

export function PaymentSplitModal({ orderId, total, onPaid, onCancel }: Props) {
  const totalNum = parseFloat(total);
  const [cashStr, setCashStr] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { toast } = useToast();

  const cashNum = useMemo(() => {
    const n = parseFloat(cashStr || "0");
    return isNaN(n) ? 0 : Math.max(0, n);
  }, [cashStr]);

  const cardNum = Math.max(0, +(totalNum - cashNum).toFixed(2));
  const isValid = cashStr !== "" && cashNum >= 0 && cashNum <= totalNum && (cashNum + cardNum) === totalNum;
  const showingCardPrompt = busy && cardNum > 0;

  const submit = async () => {
    if (!isValid) {
      setError(`Cash must be 0 – ${totalNum.toFixed(2)}`);
      return;
    }
    setError(""); setBusy(true);
    try {
      const r = await api.payment.split({
        client_id: crypto.randomUUID(),
        order_id: orderId,
        cash_amount: cashNum.toFixed(2),
        card_amount: cardNum.toFixed(2),
      });
      toast("Payment received");
      onPaid({
        transactionId: r.transaction.id,
        cashAmount: cashNum.toFixed(2),
        cardAmount: cardNum.toFixed(2),
      });
    } catch (e: any) {
      setError(e.message || "Split payment failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell onClose={onCancel} busy={busy}>
      <h3 style={{ margin: 0, marginBottom: 4 }}>Split payment</h3>
      <p style={{ margin: 0, marginBottom: spacing.md, color: colors.textSecondary, fontSize: 14 }}>
        Total to settle: <strong style={{ color: colors.textPrimary }}>€{totalNum.toFixed(2)}</strong>
      </p>

      {!showingCardPrompt && (
        <form onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <label style={modalLabelStyle}>Cash portion</label>
          <input
            autoFocus
            inputMode="decimal"
            value={cashStr}
            onChange={(e) => { setCashStr(e.target.value); setError(""); }}
            placeholder="0.00"
            style={{ ...baseStyles.input, fontSize: 22, padding: 14, fontWeight: 600, textAlign: "right" }}
          />
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: spacing.sm }}>
            {QUICK_TENDERS.filter((n) => n <= totalNum).map((n) => (
              <Button key={n} variant="secondary" size="sm" type="button" onClick={() => setCashStr(Math.min(n, totalNum).toFixed(2))}>
                €{n}
              </Button>
            ))}
            <Button variant="secondary" size="sm" type="button" onClick={() => setCashStr(totalNum.toFixed(2))}>
              All cash
            </Button>
            <Button variant="secondary" size="sm" type="button" onClick={() => setCashStr("0.00")}>
              All card
            </Button>
          </div>

          <div style={{
            marginTop: spacing.lg,
            padding: spacing.md,
            background: colors.surfaceMuted,
            borderRadius: radius.sm,
            fontSize: 14,
          }}>
            <Row label="Cash" value={`€${cashNum.toFixed(2)}`} />
            <Row label="Card" value={`€${cardNum.toFixed(2)}`} emphasized />
          </div>

          {error && (
            <div style={{
              marginTop: spacing.sm,
              background: colors.dangerSurface, color: colors.danger,
              padding: "8px 12px", borderRadius: radius.sm, fontSize: 13,
            }}>{error}</div>
          )}

          <div style={{ display: "flex", gap: spacing.sm, marginTop: spacing.md }}>
            <Button variant="ghost" fullWidth type="button" onClick={onCancel} disabled={busy}>
              Cancel
            </Button>
            <Button variant="primary" fullWidth type="submit" disabled={!isValid || busy} loading={busy}>
              {cardNum > 0 ? "Charge card" : "Confirm cash"}
            </Button>
          </div>
        </form>
      )}

      {showingCardPrompt && (
        <div style={{ textAlign: "center", padding: spacing.lg }}>
          <div style={{ fontSize: 48, marginBottom: spacing.md }}>💳</div>
          <p style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>
            Charging €{cardNum.toFixed(2)} on the terminal…
          </p>
          <p style={{ color: colors.textSecondary, fontSize: 14, marginTop: spacing.sm }}>
            Customer pays remaining €{cashNum.toFixed(2)} in cash separately.
          </p>
        </div>
      )}
    </ModalShell>
  );
}

function Row({ label, value, emphasized = false }: { label: string; value: string; emphasized?: boolean }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between",
      padding: "4px 0",
      fontWeight: emphasized ? 700 : 500,
      color: emphasized ? colors.brand : colors.textPrimary,
    }}>
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
