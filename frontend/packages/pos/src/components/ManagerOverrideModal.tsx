import { useState } from "react";
import {
  Button,
  ModalShell,
  baseStyles,
  colors,
  managerOverride,
  modalLabelStyle,
  radius,
  spacing,
} from "@openmarket/shared";
import type { ManagerOverrideResult } from "@openmarket/shared";

interface Props {
  title: string;
  description: string;
  action: string;
  context?: Record<string, unknown>;
  onAuthorized: (auth: ManagerOverrideResult) => void;
  onCancel: () => void;
}

export function ManagerOverrideModal({
  title, description, action, context, onAuthorized, onCancel,
}: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email.trim() || !password) {
      setError("Manager email and password required");
      return;
    }
    setError(""); setBusy(true);
    try {
      const auth = await managerOverride({ email: email.trim(), password, action, context });
      onAuthorized(auth);
    } catch (e: any) {
      setError(e.message || "Authorization failed");
    } finally { setBusy(false); }
  };

  return (
    <ModalShell onClose={onCancel} busy={busy}>
      <div style={{
        fontSize: 11, fontWeight: 700, color: colors.warning,
        textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4,
      }}>Manager authorization required</div>
      <h3 style={{ margin: 0, marginBottom: 4 }}>{title}</h3>
      <p style={{ margin: 0, marginBottom: spacing.md, color: colors.textSecondary, fontSize: 14 }}>
        {description}
      </p>
      <form onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <label style={modalLabelStyle}>Manager email</label>
        <input
          autoFocus
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="manager@store.local"
          style={{ ...baseStyles.input, fontSize: 16, padding: 12, marginBottom: spacing.sm }}
        />
        <label style={modalLabelStyle}>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ ...baseStyles.input, fontSize: 16, padding: 12 }}
        />
        {error && (
          <div style={{
            marginTop: spacing.sm,
            background: colors.dangerSurface, color: colors.danger,
            padding: "8px 12px", borderRadius: radius.sm, fontSize: 13,
          }}>{error}</div>
        )}
        <div style={{ display: "flex", gap: spacing.sm, marginTop: spacing.md }}>
          <Button variant="ghost" fullWidth onClick={onCancel} disabled={busy} type="button">
            Cancel
          </Button>
          <Button variant="primary" fullWidth loading={busy} type="submit">
            Authorize
          </Button>
        </div>
      </form>
    </ModalShell>
  );
}
