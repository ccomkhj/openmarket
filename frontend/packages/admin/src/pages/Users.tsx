import { useEffect, useState } from "react";
import { api } from "@openmarket/shared";

type U = {
  id: number;
  email: string | null;
  full_name: string;
  role: "owner" | "manager" | "cashier";
  active: boolean;
  created_at: string | null;
  last_login_at: string | null;
};

export function Users() {
  const [users, setUsers] = useState<U[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  async function reload() {
    try { setUsers(await api.users.list()); }
    catch (e) { setError((e as Error).message); }
  }

  useEffect(() => { void reload(); }, []);

  async function handleDeactivate(id: number) {
    if (!confirm("Deactivate this user?")) return;
    try {
      await api.users.deactivate(id);
      await reload();
    } catch (e) { setError((e as Error).message); }
  }

  return (
    <div style={{ maxWidth: 960, margin: "32px auto" }}>
      <h1>Users</h1>
      <button onClick={() => setShowNew(true)}>New user</button>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      {showNew && <NewUserForm onDone={() => { setShowNew(false); void reload(); }} />}

      <table style={{ width: "100%", marginTop: 16 }}>
        <thead><tr><th>Name</th><th>Role</th><th>Email</th><th>Active</th><th>Last login</th><th></th></tr></thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} style={{ opacity: u.active ? 1 : 0.4 }}>
              <td>{u.full_name}</td>
              <td>{u.role}</td>
              <td>{u.email ?? "(PIN only)"}</td>
              <td>{u.active ? "yes" : "no"}</td>
              <td>{u.last_login_at ?? "-"}</td>
              <td>{u.active && <button onClick={() => handleDeactivate(u.id)}>Deactivate</button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NewUserForm({ onDone }: { onDone: () => void }) {
  const [role, setRole] = useState<"manager" | "cashier" | "owner">("cashier");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (role === "cashier") {
        await api.users.create({ role, full_name: fullName, pin });
      } else {
        await api.users.create({ role, full_name: fullName, email, password });
      }
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} style={{ border: "1px solid #ccc", padding: 16, marginTop: 16 }}>
      <h2>New user</h2>
      <label>Role:
        <select value={role} onChange={(e) => setRole(e.target.value as "manager" | "cashier" | "owner")}>
          <option value="cashier">cashier</option>
          <option value="manager">manager</option>
          <option value="owner">owner</option>
        </select>
      </label>
      <br />
      <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Full name" required />
      {role === "cashier" ? (
        <input
          inputMode="numeric"
          pattern="[0-9]*"
          maxLength={6}
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          placeholder="PIN (4-6 digits)"
          required
        />
      ) : (
        <>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" required />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password (min 12)" minLength={12} required />
        </>
      )}
      <button type="submit">Create</button>
      <button type="button" onClick={onDone}>Cancel</button>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
    </form>
  );
}
