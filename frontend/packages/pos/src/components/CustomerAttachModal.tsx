import { useState } from "react";
import { api, Button, ModalShell, baseStyles, colors, modalLabelStyle, radius, spacing } from "@openmarket/shared";
import type { Customer } from "@openmarket/shared";

interface Props {
  initialPhone?: string;
  onAttach: (customer: Customer) => void;
  onClose: () => void;
}

export function CustomerAttachModal({ initialPhone = "", onAttach, onClose }: Props) {
  const [phone, setPhone] = useState(initialPhone);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  const lookup = async () => {
    const trimmed = phone.trim();
    if (!trimmed) { setError("Enter a phone number"); return; }
    setError(""); setBusy(true);
    try {
      const c = await api.customers.lookup({ phone: trimmed });
      onAttach(c);
    } catch {
      setError("No customer found with that phone — create a new one?");
      setShowCreate(true);
    } finally { setBusy(false); }
  };

  const create = async () => {
    if (!name.trim()) { setError("Name is required"); return; }
    if (!phone.trim()) { setError("Phone is required"); return; }
    const parts = name.trim().split(/\s+/);
    const first_name = parts[0];
    const last_name = parts.slice(1).join(" ");
    setError(""); setBusy(true);
    try {
      const c = await api.customers.create({
        first_name,
        last_name,
        phone: phone.trim(),
        email: email.trim() || null,
      });
      onAttach(c);
    } catch (e: any) {
      setError(e.message || "Could not create customer");
    } finally { setBusy(false); }
  };

  return (
    <ModalShell onClose={onClose} busy={busy}>
      <h3 style={{ margin: 0, marginBottom: spacing.md }}>Attach customer</h3>
      <label style={modalLabelStyle}>Phone</label>
      <input
        autoFocus
        value={phone}
        onChange={(e) => { setPhone(e.target.value); setShowCreate(false); }}
        onKeyDown={(e) => { if (e.key === "Enter" && !showCreate) lookup(); }}
        placeholder="+49 30 1234567"
        style={{ ...baseStyles.input, fontSize: 16, padding: 12 }}
      />

      {!showCreate && (
        <>
          <Button variant="primary" fullWidth loading={busy} onClick={lookup} style={{ marginTop: spacing.md }}>
            Look up
          </Button>
          <Button variant="secondary" fullWidth onClick={() => setShowCreate(true)} style={{ marginTop: spacing.sm }}>
            + New customer
          </Button>
        </>
      )}

      {showCreate && (
        <form
          onSubmit={(e) => { e.preventDefault(); create(); }}
          style={{ marginTop: spacing.md, display: "flex", flexDirection: "column", gap: spacing.sm }}
        >
          <div>
            <label style={modalLabelStyle}>Full name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Doe"
              style={{ ...baseStyles.input, fontSize: 16, padding: 12 }}
            />
          </div>
          <div>
            <label style={modalLabelStyle}>Email (optional)</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@example.com"
              style={{ ...baseStyles.input, fontSize: 16, padding: 12 }}
            />
          </div>
          <Button type="submit" variant="primary" fullWidth loading={busy}>Create &amp; attach</Button>
        </form>
      )}

      {error && (
        <div style={{
          marginTop: spacing.md,
          background: colors.warningSurface, color: colors.warning,
          padding: "8px 12px", borderRadius: radius.sm, fontSize: 13,
        }}>{error}</div>
      )}

      <Button variant="ghost" fullWidth onClick={onClose} style={{ marginTop: spacing.md }}>
        Cancel
      </Button>
    </ModalShell>
  );
}
