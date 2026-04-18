import { useState } from "react";
import { login } from "@openmarket/shared";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfa, setMfa] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const r = await login(email, password, mfaRequired ? mfa : undefined);
      if (r.mfa_required) {
        setMfaRequired(true);
        return;
      }
      onSuccess();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} style={{ maxWidth: 320, margin: "10vh auto" }}>
      <h1>OpenMarket Admin</h1>
      <input autoFocus type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" required />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" required />
      {mfaRequired && (
        <input type="text" inputMode="numeric" pattern="[0-9]*" value={mfa} onChange={(e) => setMfa(e.target.value)} placeholder="6-digit MFA code" required />
      )}
      <button type="submit">Sign in</button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
