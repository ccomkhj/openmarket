import { useState } from "react";
import { setup } from "@openmarket/shared";

export function Setup({ onComplete }: { onComplete: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await setup(email, password, fullName);
      onComplete();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} style={{ maxWidth: 320, margin: "10vh auto" }}>
      <h1>First-Run Setup</h1>
      <p>Create the owner account. This page disappears once set up.</p>
      <input autoFocus value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Full name" required />
      <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" required />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password (min 12 chars)" minLength={12} required />
      <button type="submit">Create owner</button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
