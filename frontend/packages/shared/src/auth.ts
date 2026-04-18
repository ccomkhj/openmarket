export type Me = {
  id: number;
  email: string | null;
  full_name: string;
  role: "owner" | "manager" | "cashier";
};

const base = "/api/auth";

export async function fetchMe(): Promise<Me | null> {
  const r = await fetch(`${base}/me`, { credentials: "include" });
  if (r.status === 401) return null;
  if (!r.ok) throw new Error(`auth.me failed: ${r.status}`);
  return (await r.json()) as Me;
}

export async function login(email: string, password: string, totp?: string) {
  const r = await fetch(`${base}/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, totp_code: totp ?? null }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail ?? "login failed");
  return body as { user_id: number; role: string; mfa_required: boolean };
}

export async function logout() {
  await fetch(`${base}/logout`, { method: "POST", credentials: "include" });
}

export async function setup(email: string, password: string, full_name: string) {
  const r = await fetch(`${base}/setup`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail ?? "setup failed");
  return body;
}

export async function posLogin(userId: number, pin: string) {
  const r = await fetch(`${base}/pos-login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, pin }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail ?? "login failed");
  return body;
}

export type BootstrapStatus = { setup_required: boolean };

export async function fetchBootstrapStatus(): Promise<BootstrapStatus> {
  const r = await fetch(`${base}/bootstrap-status`, { credentials: "include" });
  if (!r.ok) throw new Error(`bootstrap-status failed: ${r.status}`);
  return (await r.json()) as BootstrapStatus;
}
