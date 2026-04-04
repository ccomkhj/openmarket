import { Button, colors, spacing, radius } from "@openmarket/shared";

export interface ReceiptItem {
  productTitle: string;
  variantTitle: string;
  quantity: number;
  price: string;
}

interface ReceiptProps {
  orderNumber: string;
  items: ReceiptItem[];
  total: number;
  onClose: () => void;
}

export function Receipt({ orderNumber, items, total, onClose }: ReceiptProps) {
  const timestamp = new Date().toLocaleString();

  return (
    <>
      <style>{`
        @media print {
          body > * { display: none !important; }
          .receipt-printable { display: block !important; position: static !important; background: white !important; }
          .receipt-printable * { color: black !important; }
          .receipt-no-print { display: none !important; }
        }
      `}</style>
      <div
        className="receipt-no-print"
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
        }}
        onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      >
        <div
          className="receipt-printable"
          style={{
            background: colors.surface,
            borderRadius: radius.lg,
            padding: spacing.lg,
            width: 360,
            maxHeight: "90vh",
            overflowY: "auto",
            boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
          }}
        >
          {/* Header */}
          <div style={{ textAlign: "center", marginBottom: spacing.md, borderBottom: `1px dashed ${colors.border}`, paddingBottom: spacing.md }}>
            <h2 style={{ margin: 0, fontSize: "20px", fontWeight: 700, color: colors.brand }}>OpenMarket</h2>
            <p style={{ margin: "4px 0 0", fontSize: "14px", color: colors.textSecondary }}>Receipt</p>
          </div>

          {/* Order Info */}
          <div style={{ marginBottom: spacing.md, fontSize: "13px", color: colors.textSecondary }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Order #</span>
              <span style={{ fontWeight: 600, color: colors.textPrimary }}>{orderNumber}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px" }}>
              <span>Date</span>
              <span>{timestamp}</span>
            </div>
          </div>

          {/* Line Items */}
          <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: spacing.md, marginBottom: spacing.md }}>
            {items.map((item, idx) => {
              const lineTotal = (parseFloat(item.price) * item.quantity).toFixed(2);
              return (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "10px",
                    fontSize: "14px",
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>{item.productTitle}</div>
                    <div style={{ color: colors.textSecondary, fontSize: "12px" }}>
                      {item.variantTitle} × {item.quantity} @ ${item.price}
                    </div>
                  </div>
                  <div style={{ fontWeight: 600, marginLeft: spacing.md }}>${lineTotal}</div>
                </div>
              );
            })}
          </div>

          {/* Total */}
          <div style={{
            borderTop: `2px solid ${colors.textPrimary}`,
            paddingTop: spacing.md,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: spacing.md,
          }}>
            <span style={{ fontWeight: 700, fontSize: "16px" }}>Total</span>
            <span style={{ fontWeight: 700, fontSize: "24px" }}>${total.toFixed(2)}</span>
          </div>

          {/* Thank You */}
          <div style={{ textAlign: "center", marginBottom: spacing.lg, color: colors.textSecondary, fontSize: "14px" }}>
            Thank you for your purchase!
          </div>

          {/* Buttons */}
          <div className="receipt-no-print" style={{ display: "flex", gap: spacing.sm }}>
            <Button
              variant="primary"
              size="md"
              fullWidth
              onClick={() => window.print()}
            >
              Print Receipt
            </Button>
            <Button
              variant="secondary"
              size="md"
              fullWidth
              onClick={onClose}
            >
              Close
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
