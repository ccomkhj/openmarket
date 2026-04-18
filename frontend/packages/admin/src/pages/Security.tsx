import { useState } from "react";
import { mfaEnroll, mfaVerify } from "@openmarket/shared";

export function Security() {
  const [phase, setPhase] = useState<"idle" | "enrolled" | "verified">("idle");
  const [secret, setSecret] = useState<string | null>(null);
  const [uri, setUri] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function startEnroll() {
    setError(null);
    try {
      const res = await mfaEnroll();
      setSecret(res.secret);
      setUri(res.uri);
      setPhase("enrolled");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await mfaVerify(code);
      setPhase("verified");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div style={{ maxWidth: 520, margin: "32px auto" }}>
      <h1>Security</h1>
      <h2>Two-factor authentication (TOTP)</h2>

      {phase === "idle" && (
        <>
          <p>
            Enroll a TOTP authenticator (Authy, 1Password, Aegis) to protect this
            owner account. MFA is required for owner role.
          </p>
          <button onClick={startEnroll}>Enroll MFA</button>
        </>
      )}

      {phase === "enrolled" && uri && secret && (
        <>
          <p>
            Scan this URI into your authenticator, then enter the current
            6-digit code to confirm.
          </p>
          <pre style={{ wordBreak: "break-all", background: "#f4f4f4", padding: 12 }}>{uri}</pre>
          <p>Or enter the secret manually: <code>{secret}</code></p>
          <form onSubmit={verify}>
            <input
              autoFocus
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="6-digit code"
              required
            />
            <button type="submit">Verify</button>
          </form>
        </>
      )}

      {phase === "verified" && <p>MFA enrolled and verified. You&apos;ll be prompted on next login.</p>}

      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
    </div>
  );
}
