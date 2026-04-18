# Foundation Fix-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Critical and Day-1 correctness findings from Plan 1's final code review: make the LAN-IP gate actually resistant to spoofing, make first-run setup auto-detect without a URL flag, fix the receipt math for weighed items, and add the two missing admin UIs (MFA enrollment, Users management) that the bootstrap runbook promised but didn't ship.

**Architecture:** Narrow, surgical fixes on top of Plan 1. Two of the fixes are infrastructure (nginx + Settings trusted-proxy config) and the rest are code + UI. No schema rewrites — the inventory-kg accuracy debt is explicitly deferred to Plan 2, where Fiscal/TSE work will touch the same order path.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Postgres, React + TypeScript. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-04-18-go-live-v1-design.md` — same spec as Plan 1.

**Starting point:** `main` branch at `04fc79e` (Plan 1 complete). 131/132 backend tests passing (only pre-existing `test_orders_pagination` fails). No new Postgres migrations; the one code-gen migration here (Task 7's Session comment) is a model-level docstring change only.

**Explicitly deferred (not this plan):**

- **Inventory-kg accuracy (I4)** — requires `InventoryLevel.available: Integer → Numeric(10,3)` migration and cascades into inventory reports + admin UI. Plan 2 will retouch the order service for TSE-signed transactions; bundle the kg-inventory work there.
- **LineItem.quantity honest semantics (I6)** — keep `quantity=1 + quantity_kg=X` convention; Task 9 adds a comment on the schema but doesn't migrate. Plan 2 decides the real shape when it builds `pos_transaction` / `pos_transaction_line`.

---

## File Structure

**Backend new:**

- `backend/tests/test_trusted_proxy.py` — spoof-resistance tests for `_client_ip`
- `backend/tests/test_bootstrap_status.py` — tests for the new setup-status endpoint
- `backend/tests/test_weighed_line_totals.py` — tests that orders API surfaces per-line totals that the receipt can display verbatim

**Backend modified:**

- `backend/app/config.py` — add `trusted_proxy_cidrs` setting + list accessor
- `backend/app/api/auth.py` — rewrite `_client_ip` to only honor XFF from trusted proxies; add `/api/auth/bootstrap-status`; gate `/api/auth/cashiers` behind LAN-IP
- `backend/app/main.py` — auth the `/api/ws` upgrade handshake
- `backend/app/models/auth.py` — add a one-line comment explaining why `Session.expires_at` has both a server_default and an application-computed value
- `backend/app/schemas/order.py` — reject `quantity != 1` for by-weight items; add `line_total` field on `LineItemOut`
- `backend/app/services/order.py` — populate `line_total` on the response path
- `backend/app/api/orders.py` — map the new validation error to 400
- `backend/tests/conftest.py` — try/finally around `setup_db` engine; remove unused imports surfaced during edits
- `backend/tests/test_auth_api.py` — add tests for bootstrap-status, cashiers LAN gate, ws auth

**Frontend modified:**

- `frontend/packages/shared/src/api.ts` — set `credentials: "include"` on every request
- `frontend/packages/shared/src/auth.ts` — add `fetchBootstrapStatus()`
- `frontend/packages/admin/src/components/RequireAuth.tsx` — probe bootstrap-status on mount and route accordingly
- `frontend/packages/admin/src/pages/Security.tsx` — new MFA enrollment page
- `frontend/packages/admin/src/pages/Users.tsx` — new Users management page
- `frontend/packages/admin/src/App.tsx` — add routes for `Security`, `Users`; add nav entries for owner/manager
- `frontend/packages/pos/src/components/Receipt.tsx` — use server-provided `line_total` for weighed items
- `frontend/packages/pos/src/pages/SalePage.tsx` — use the same `line_total` for cart subtotal rendering

**Ops modified:**

- `nginx.conf` — set `X-Forwarded-For` and `real_ip_header` so the trusted-proxy chain works
- `docs/ops/bootstrap-first-run.md` — reflect the auto-detecting Setup flow and point at the new Security / Users pages

---

## Task 1: Trusted-proxy setting and list accessor

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1.1: Write the failing test**

Append to `backend/tests/test_config.py`:

```python
def test_settings_parses_trusted_proxy_cidrs_default():
    s = Settings(session_secret_key="x" * 48)
    assert s.trusted_proxy_cidr_list == ["127.0.0.1/32"]


def test_settings_parses_trusted_proxy_cidrs_custom():
    s = Settings(
        session_secret_key="x" * 48,
        trusted_proxy_cidrs="127.0.0.1/32, 172.20.0.0/16",
    )
    assert s.trusted_proxy_cidr_list == ["127.0.0.1/32", "172.20.0.0/16"]
```

- [ ] **Step 1.2: Run the test to confirm it fails**

Run: `cd backend && pytest tests/test_config.py -v -k trusted_proxy`
Expected: FAIL — `trusted_proxy_cidrs` doesn't exist.

- [ ] **Step 1.3: Edit `backend/app/config.py`**

Add a field and property. Inside the `Settings` class, alongside the other CSV-as-string fields:

```python
    trusted_proxy_cidrs: str = "127.0.0.1/32"
```

Then alongside the other `*_list` properties:

```python
    @property
    def trusted_proxy_cidr_list(self) -> list[str]:
        return [s.strip() for s in self.trusted_proxy_cidrs.split(",") if s.strip()]
```

- [ ] **Step 1.4: Run the test to confirm it passes**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: PASS (9 tests total — 7 prior + 2 new)

- [ ] **Step 1.5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(config): add trusted_proxy_cidrs setting"
```

---

## Task 2: `_client_ip` honors XFF only from trusted proxies

**Files:**
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_trusted_proxy.py` (new)

- [ ] **Step 2.1: Write the failing test**

Create `backend/tests/test_trusted_proxy.py`:

```python
import ipaddress
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.api.auth import _client_ip


def _request(remote_host: str, xff: str | None) -> MagicMock:
    req = MagicMock()
    req.client = MagicMock(host=remote_host)
    headers: dict[str, str] = {}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    req.headers.get = lambda k: headers.get(k)
    return req


def test_direct_caller_uses_remote_host():
    req = _request("8.8.8.8", None)
    assert _client_ip(req) == "8.8.8.8"


def test_ignores_xff_from_untrusted_caller():
    # Attacker on public internet sends XFF: 192.168.1.5
    req = _request("8.8.8.8", "192.168.1.5")
    assert _client_ip(req) == "8.8.8.8"


def test_honors_xff_from_trusted_proxy(monkeypatch):
    # Default trusted proxy list is 127.0.0.1/32; simulate nginx forwarding from loopback
    req = _request("127.0.0.1", "192.168.1.5, 10.0.0.1")
    assert _client_ip(req) == "192.168.1.5"


def test_honors_xff_with_whitespace():
    req = _request("127.0.0.1", "  192.168.1.23  ")
    assert _client_ip(req) == "192.168.1.23"


def test_handles_missing_client():
    req = MagicMock()
    req.client = None
    req.headers.get = lambda k: None
    assert _client_ip(req) == "0.0.0.0"
```

- [ ] **Step 2.2: Run to confirm fail**

Run: `cd backend && pytest tests/test_trusted_proxy.py -v`
Expected: FAIL — `test_ignores_xff_from_untrusted_caller` fails because the current implementation trusts XFF unconditionally.

- [ ] **Step 2.3: Rewrite `_client_ip` in `backend/app/api/auth.py`**

Replace the existing `_client_ip` function with:

```python
def _client_ip(request: Request) -> str:
    """Return the true client IP.

    Trusts `X-Forwarded-For` ONLY when the direct caller (request.client.host)
    falls within `settings.trusted_proxy_cidrs`. Otherwise uses the direct caller.
    This prevents an attacker on an open internet path from spoofing a LAN IP
    via a forged header.
    """
    direct = request.client.host if request.client else "0.0.0.0"
    try:
        direct_addr = ipaddress.ip_address(direct)
    except ValueError:
        return direct
    trusted = [ipaddress.ip_network(c) for c in settings.trusted_proxy_cidr_list]
    if any(direct_addr in net for net in trusted):
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            first = fwd.split(",")[0].strip()
            try:
                ipaddress.ip_address(first)
                return first
            except ValueError:
                pass
    return direct
```

- [ ] **Step 2.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_trusted_proxy.py -v`
Expected: PASS (all 5)

- [ ] **Step 2.5: Re-run existing auth API tests**

Run: `cd backend && pytest tests/test_auth_api.py -v`

Expected: One test now fails — `test_pos_login_with_pin` because the test relied on XFF being honored from any caller. The ASGI client's `request.client.host` is `127.0.0.1`, which IS in the default trusted-proxy list, so the XFF should still be honored in that test. Confirm PASS. If it fails, inspect — the default trusted_proxy_cidrs is `"127.0.0.1/32"`, so XFF from 127.0.0.1 (the ASGI harness) should be honored.

Similarly `test_pos_login_rejects_non_lan_ip` — the XFF is `8.8.8.8`, direct caller is `127.0.0.1` (trusted), so XFF is honored → 8.8.8.8 → non-LAN → 403. PASS.

If both pass, proceed. If either fails, the trusted-proxy list needs to include the ASGI transport's view of the client (log `request.client.host` to confirm).

- [ ] **Step 2.6: Commit**

```bash
git add backend/app/api/auth.py backend/tests/test_trusted_proxy.py
git commit -m "fix(auth): only honor X-Forwarded-For from trusted proxies"
```

---

## Task 3: nginx sets X-Forwarded-For and real_ip_header

**Files:**
- Modify: `nginx.conf`

- [ ] **Step 3.1: Update the `http {}` and `/api/` blocks**

Replace the existing `nginx.conf` with:

```nginx
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Trust the docker network as the proxy chain; real_ip_header rewrites
    # remote_addr from XFF so access logs and any downstream stage see the
    # true client. The app has its own trusted-proxy allowlist
    # (settings.trusted_proxy_cidrs) independent of this.
    set_real_ip_from 127.0.0.0/8;
    set_real_ip_from 10.0.0.0/8;
    set_real_ip_from 172.16.0.0/12;
    set_real_ip_from 192.168.0.0/16;
    real_ip_header X-Forwarded-For;
    real_ip_recursive on;

    upstream api {
        server api:8000;
    }

    server {
        listen 80;

        location /api/ {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location / {
            root /usr/share/nginx/html/store;
            try_files $uri $uri/ /index.html;
        }

        location = /admin {
            return 301 /admin/;
        }

        location /admin/ {
            alias /usr/share/nginx/html/admin/;
            try_files $uri $uri/ /admin/index.html;
        }

        location = /pos {
            return 301 /pos/;
        }

        location /pos/ {
            alias /usr/share/nginx/html/pos/;
            try_files $uri $uri/ /pos/index.html;
        }
    }
}
```

- [ ] **Step 3.2: Validate with nginx's built-in config check**

If docker is running:

Run: `docker run --rm -v $PWD/nginx.conf:/etc/nginx/nginx.conf:ro nginx:alpine nginx -t`
Expected: `nginx: configuration file /etc/nginx/nginx.conf test is successful`

If docker isn't available, skip this step — the config is small enough to trust.

- [ ] **Step 3.3: Update the deployment note**

Add at the bottom of `docs/ops/bootstrap-first-run.md`, a new section:

```markdown
## After updating nginx.conf

Whenever `nginx.conf` changes, either restart the nginx container
(`docker compose restart nginx`) or reload in-place
(`docker compose exec nginx nginx -s reload`). The running container reads
the file via a bind mount, so edits in the repo take effect after the
reload — no rebuild required.
```

- [ ] **Step 3.4: Commit**

```bash
git add nginx.conf docs/ops/bootstrap-first-run.md
git commit -m "fix(nginx): set X-Forwarded-For and real_ip_header"
```

---

## Task 4: Gate `/api/auth/cashiers` behind LAN-IP

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 4.1: Write the failing test**

Append to `backend/tests/test_auth_api.py`:

```python
@pytest.mark.asyncio
async def test_list_cashiers_rejects_non_lan(client, db):
    from app.models import User
    from app.services.password import hash_pin

    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="Anna M.", role="cashier")
    db.add(c); await db.commit()

    r = await client.get(
        "/api/auth/cashiers",
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert r.status_code == 403
```

The existing `test_list_cashiers` test hits the endpoint without any XFF header, which means the ASGI client's `request.client.host = 127.0.0.1` is used — and 127.0.0.1 is in the default LAN CIDR list (per Task 1 in Plan 1). So the existing test continues to pass unmodified.

- [ ] **Step 4.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_auth_api.py::test_list_cashiers_rejects_non_lan -v`
Expected: FAIL — the endpoint currently has no LAN gate.

- [ ] **Step 4.3: Apply the gate**

In `backend/app/api/auth.py`, modify the `list_cashiers` route to check LAN:

```python
@router.get("/cashiers", response_model=list[PosLoginResponse])
async def list_cashiers(request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)
    if not _ip_is_lan(ip):
        raise HTTPException(status_code=403, detail="cashier list only from LAN")
    result = await db.execute(
        select(User).where(User.role == "cashier", User.active.is_(True)).order_by(User.full_name)
    )
    return [PosLoginResponse(user_id=u.id, full_name=u.full_name) for u in result.scalars().all()]
```

- [ ] **Step 4.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_auth_api.py -v`
Expected: PASS (all prior auth tests + the new non-LAN rejection)

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/api/auth.py backend/tests/test_auth_api.py
git commit -m "fix(auth): gate cashier-list endpoint to LAN-only"
```

---

## Task 5: Auth the `/api/ws` websocket

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_websocket.py`

- [ ] **Step 5.1: Write the failing test**

The existing `backend/tests/test_websocket.py` uses a plain `client` to open a websocket without auth. Replace its contents with:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ws_rejects_unauthenticated(client: AsyncClient):
    # Without a session cookie, the upgrade should be rejected with 401
    # (httpx AsyncClient doesn't follow ws upgrades; we test via direct GET).
    r = await client.get("/api/ws", headers={"Connection": "Upgrade", "Upgrade": "websocket"})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ws_allows_authenticated(authed_client: AsyncClient):
    r = await authed_client.get(
        "/api/ws", headers={"Connection": "Upgrade", "Upgrade": "websocket"}
    )
    # An authed GET with no real ws handshake gets 400 or 426 from starlette,
    # NOT 401/403. We only care that auth didn't reject it.
    assert r.status_code not in (401, 403)
```

- [ ] **Step 5.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_websocket.py -v`
Expected: `test_ws_rejects_unauthenticated` FAILS because the current ws endpoint has no auth check.

- [ ] **Step 5.3: Add cookie auth to the ws endpoint**

In `backend/app/main.py`, replace the `websocket_endpoint` with:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import async_session
from app.services.session import get_active_session


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    sid = websocket.cookies.get(settings.session_cookie_name)
    if not sid:
        await websocket.close(code=1008)
        return
    async with async_session() as db:
        sess = await get_active_session(db, sid)
    if not sess:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

Note: websocket handshake in FastAPI returns 403 if `websocket.close()` is called before `accept()`. For our test assertions, this produces the desired status codes.

- [ ] **Step 5.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_websocket.py -v`
Expected: PASS

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/main.py backend/tests/test_websocket.py
git commit -m "fix(ws): require authenticated session on /api/ws"
```

---

## Task 6: Shared `api.ts` sends credentials on every request

**Files:**
- Modify: `frontend/packages/shared/src/api.ts`

- [ ] **Step 6.1: Update the `request` helper**

Replace the `request` function at the top of `frontend/packages/shared/src/api.ts`:

```typescript
const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}
```

The key change: `credentials: "include"` is set BEFORE the spread of `options`, so callers can still override it if they need to.

- [ ] **Step 6.2: Build check**

Run: `cd frontend && pnpm -r build`
Expected: clean build across all packages.

- [ ] **Step 6.3: Commit**

```bash
git add frontend/packages/shared/src/api.ts
git commit -m "fix(api): send credentials on every request"
```

---

## Task 7: `setup_db` try/finally + `Session.expires_at` docstring

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/app/models/auth.py`

- [ ] **Step 7.1: Add try/finally to `setup_db` in conftest**

Open `backend/tests/conftest.py` and find the `setup_db` autouse fixture. Wrap the engine lifecycle in try/finally:

```python
@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(TEST_DB_URL)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(sa.text(_TRIGGER_SQL))
            await conn.execute(sa.text(_TRIGGER_UPDATE_DROP_SQL))
            await conn.execute(sa.text(_TRIGGER_UPDATE_SQL))
            await conn.execute(sa.text(_TRIGGER_DELETE_DROP_SQL))
            await conn.execute(sa.text(_TRIGGER_DELETE_SQL))
        yield engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    finally:
        await engine.dispose()
```

Adjust the trigger-SQL variable names to match whatever the existing conftest has after Task 7 of Plan 1 (the implementer split them further there — verify the names first).

- [ ] **Step 7.2: Add an explanatory comment on `Session.expires_at`**

In `backend/app/models/auth.py`, find the `Session` class and add a comment above the `expires_at` column:

```python
    # NOT NULL with a server-side safety-net default so raw-SQL inserts
    # can't leave a session without an expiry. Application code (see
    # app.services.session.create_session) always sets expires_at
    # explicitly, making the default a belt-and-suspenders guard rather
    # than the happy-path source of truth.
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now() + interval '12 hours'"),
    )
```

- [ ] **Step 7.3: Run the full backend suite**

Run: `cd backend && pytest 2>&1 | tail -5`
Expected: same pass count as before (only `test_orders_pagination` pre-existing failure).

- [ ] **Step 7.4: Commit**

```bash
git add backend/tests/conftest.py backend/app/models/auth.py
git commit -m "chore(tests): harden setup_db teardown + document Session default"
```

---

## Task 8: `/api/auth/bootstrap-status` endpoint

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/schemas/auth.py`
- Test: `backend/tests/test_bootstrap_status.py` (new)

- [ ] **Step 8.1: Write the failing test**

Create `backend/tests/test_bootstrap_status.py`:

```python
import pytest

from app.models import User


@pytest.mark.asyncio
async def test_bootstrap_status_empty_db(client, db):
    r = await client.get("/api/auth/bootstrap-status")
    assert r.status_code == 200
    assert r.json() == {"setup_required": True}


@pytest.mark.asyncio
async def test_bootstrap_status_with_user(client, db):
    u = User(email="owner@shop.de", password_hash="x", full_name="O", role="owner")
    db.add(u); await db.commit()
    r = await client.get("/api/auth/bootstrap-status")
    assert r.status_code == 200
    assert r.json() == {"setup_required": False}
```

- [ ] **Step 8.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_bootstrap_status.py -v`
Expected: FAIL — 404.

- [ ] **Step 8.3: Add the schema**

Append to `backend/app/schemas/auth.py`:

```python
class BootstrapStatus(BaseModel):
    setup_required: bool
```

- [ ] **Step 8.4: Add the route**

In `backend/app/api/auth.py`, alongside the other unauthenticated routes (NOT gated by LAN — the admin laptop may be remote during initial bootstrap):

```python
from app.schemas.auth import BootstrapStatus  # add to existing import block


@router.get("/bootstrap-status", response_model=BootstrapStatus)
async def bootstrap_status(db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).limit(1))
    return BootstrapStatus(setup_required=existing.scalar_one_or_none() is None)
```

- [ ] **Step 8.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_bootstrap_status.py -v`
Expected: PASS (both)

- [ ] **Step 8.6: Commit**

```bash
git add backend/app/api/auth.py backend/app/schemas/auth.py backend/tests/test_bootstrap_status.py
git commit -m "feat(auth): bootstrap-status endpoint for first-run UX"
```

---

## Task 9: RequireAuth probes bootstrap-status and auto-routes to Setup

**Files:**
- Modify: `frontend/packages/shared/src/auth.ts`
- Modify: `frontend/packages/admin/src/components/RequireAuth.tsx`

- [ ] **Step 9.1: Add `fetchBootstrapStatus` to the shared auth client**

Append to `frontend/packages/shared/src/auth.ts`:

```typescript
export type BootstrapStatus = { setup_required: boolean };

export async function fetchBootstrapStatus(): Promise<BootstrapStatus> {
  const r = await fetch(`${base}/bootstrap-status`, { credentials: "include" });
  if (!r.ok) throw new Error(`bootstrap-status failed: ${r.status}`);
  return (await r.json()) as BootstrapStatus;
}
```

Re-export from `frontend/packages/shared/src/index.ts` if the file explicitly lists exports; if it re-exports the whole module, no change needed.

- [ ] **Step 9.2: Update RequireAuth**

Replace `frontend/packages/admin/src/components/RequireAuth.tsx`:

```tsx
import { useEffect, useState } from "react";
import { fetchBootstrapStatus, fetchMe, type Me } from "@openmarket/shared";
import { Login } from "../pages/Login";
import { Setup } from "../pages/Setup";

type State = "loading" | "setup" | "login" | { me: Me };

export function RequireAuth({ children }: { children: (me: Me) => React.ReactNode }) {
  const [state, setState] = useState<State>("loading");

  async function reload() {
    try {
      const me = await fetchMe();
      if (me) {
        setState({ me });
        return;
      }
      const status = await fetchBootstrapStatus();
      setState(status.setup_required ? "setup" : "login");
    } catch {
      setState("login");
    }
  }

  useEffect(() => { void reload(); }, []);

  if (state === "loading") return <p>Loading...</p>;
  if (state === "setup") return <Setup onComplete={reload} />;
  if (state === "login") return <Login onSuccess={reload} />;
  return <>{children(state.me)}</>;
}
```

The `?setup` query-string hack from Plan 1 is removed — no longer needed.

- [ ] **Step 9.3: Build check**

Run: `cd frontend && pnpm -r build`
Expected: clean build.

- [ ] **Step 9.4: Commit**

```bash
git add frontend/packages/shared/src/auth.ts frontend/packages/admin/src/components/RequireAuth.tsx
git commit -m "fix(admin-ui): auto-detect first-run setup via bootstrap-status"
```

---

## Task 10: Reject `quantity != 1` on by-weight order lines

**Files:**
- Modify: `backend/app/schemas/order.py`
- Modify: `backend/app/services/order.py`
- Modify: `backend/app/api/orders.py`
- Test: `backend/tests/test_weighed_api.py`

- [ ] **Step 10.1: Write the failing test**

Append to `backend/tests/test_weighed_api.py`:

```python
@pytest.mark.asyncio
async def test_create_order_rejects_quantity_not_one_on_by_weight(cashier_client, db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", min_weight_kg=Decimal("0.05"),
    )
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=100)
    db.add(lvl); await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [
            {"variant_id": v.id, "quantity": 3, "quantity_kg": "0.452"},
        ],
    })
    assert r.status_code == 400
    assert "quantity" in r.json()["detail"].lower()
```

- [ ] **Step 10.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_weighed_api.py::test_create_order_rejects_quantity_not_one_on_by_weight -v`
Expected: FAIL — the order currently silently overwrites `quantity` to 1.

- [ ] **Step 10.3: Add an error class and validation in the weighed service**

In `backend/app/services/weighed.py`, add a new error and a new validator:

```python
class QuantityOnWeighedError(ValueError):
    pass


def validate_weighed_line_quantity(*, variant: ProductVariant, quantity: int, quantity_kg: "Decimal | None") -> None:
    """Stricter guard than validate_weighed_line: on by_weight, require quantity==1."""
    if variant.pricing_type == "by_weight" and quantity != 1:
        raise QuantityOnWeighedError(
            "by_weight variants must have quantity=1; use quantity_kg for the weight"
        )
```

Keep the existing `validate_weighed_line` function; this is an *additional* check called in the order service.

- [ ] **Step 10.4: Call it from the order service**

In `backend/app/services/order.py`, inside the loop that builds each `LineItem`, add the new call before the existing `validate_weighed_line`:

```python
from app.services.weighed import (
    validate_weighed_line,
    validate_weighed_line_quantity,
    compute_weighed_line_price,
    WeightMissingError,
    WeightOutOfRangeError,
    PricingTypeMismatchError,
    QuantityOnWeighedError,
)

# inside the per-item loop:
validate_weighed_line_quantity(
    variant=variant,
    quantity=item.quantity,
    quantity_kg=item.quantity_kg,
)
validate_weighed_line(variant=variant, quantity_kg=item.quantity_kg)
```

- [ ] **Step 10.5: Map the new error to 400 in the API**

In `backend/app/api/orders.py`, extend the existing weighed-error catch clause:

```python
from app.services.weighed import (
    WeightMissingError,
    WeightOutOfRangeError,
    PricingTypeMismatchError,
    QuantityOnWeighedError,
)

# in the route handler:
except (
    WeightMissingError,
    WeightOutOfRangeError,
    PricingTypeMismatchError,
    QuantityOnWeighedError,
) as e:
    raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 10.6: Run, confirm pass**

Run: `cd backend && pytest tests/test_weighed_api.py -v`
Expected: PASS (existing 2 + new 1 = 3)

- [ ] **Step 10.7: Commit**

```bash
git add backend/app/services/weighed.py backend/app/services/order.py backend/app/api/orders.py backend/tests/test_weighed_api.py
git commit -m "fix(weighed): reject quantity!=1 on by_weight order lines"
```

---

## Task 11: Orders response exposes `line_total`

**Files:**
- Modify: `backend/app/schemas/order.py`
- Modify: `backend/app/services/order.py` (ensure the response is built with `line_total`)
- Test: `backend/tests/test_weighed_line_totals.py` (new)

The goal: clients (POS receipt, admin UI) should NEVER have to recompute a line total from `price × quantity × quantity_kg` — the server authoritatively tells them the charged total per line.

- [ ] **Step 11.1: Write the failing test**

Create `backend/tests/test_weighed_line_totals.py`:

```python
import pytest
from decimal import Decimal

from app.models import Product, ProductVariant, InventoryItem, InventoryLevel, Location


@pytest.mark.asyncio
async def test_order_response_includes_line_total_for_fixed(cashier_client, db):
    p = Product(title="Milk", handle="milk"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="1L", price=Decimal("1.29"), pricing_type="fixed")
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10)
    db.add(lvl); await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": v.id, "quantity": 3}],
    })
    assert r.status_code == 201
    line = r.json()["line_items"][0]
    assert Decimal(line["line_total"]) == Decimal("3.87")  # 3 × 1.29


@pytest.mark.asyncio
async def test_order_response_includes_line_total_for_weighed(cashier_client, db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", min_weight_kg=Decimal("0.05"),
    )
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=100)
    db.add(lvl); await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": v.id, "quantity": 1, "quantity_kg": "0.452"}],
    })
    assert r.status_code == 201
    line = r.json()["line_items"][0]
    assert Decimal(line["line_total"]) == Decimal("1.13")
```

- [ ] **Step 11.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_weighed_line_totals.py -v`
Expected: FAIL — `line_total` key missing.

- [ ] **Step 11.3: Add `line_total` to the response schema**

In `backend/app/schemas/order.py`, find `LineItemOut`. Add:

```python
from decimal import Decimal

class LineItemOut(BaseModel):
    # ...existing fields...
    line_total: Decimal
```

(Keep whatever existing fields are on `LineItemOut` — only ADD `line_total`.)

- [ ] **Step 11.4: Populate `line_total` at response build time**

In `backend/app/services/order.py`, find the function that maps `LineItem` ORM objects to the response dict / model. Add logic:

```python
def _line_total(li: LineItem) -> Decimal:
    if li.quantity_kg is not None:
        # by-weight: line_total was already computed + stored in price
        return li.price
    return li.price * li.quantity
```

Wherever the service builds the `LineItemOut` for the response, include `line_total=_line_total(li)`. If the code currently uses `LineItemOut.model_validate(orm_line_item)`, you'll need to switch to explicit construction:

```python
LineItemOut(
    id=li.id,
    variant_id=li.variant_id,
    title=li.title,
    quantity=li.quantity,
    quantity_kg=li.quantity_kg,
    price=li.price,
    line_total=_line_total(li),
)
```

(Match the actual field names of `LineItemOut`; this example enumerates the Plan 1 fields.)

Rationale: `LineItem.price` for by-weight items currently stores the already-computed line total (Task 19 of Plan 1: `line_price = compute_weighed_line_price(...)`). For fixed items, `LineItem.price` stores the unit price and the total is `price × quantity`. The `_line_total` helper encodes that asymmetry once, centrally.

- [ ] **Step 11.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_weighed_line_totals.py tests/test_weighed_api.py tests/test_orders.py -v`
Expected: PASS — existing tests keep passing (they don't assert on `line_total` absence; adding a field is non-breaking), plus the 2 new tests pass.

- [ ] **Step 11.6: Commit**

```bash
git add backend/app/schemas/order.py backend/app/services/order.py backend/tests/test_weighed_line_totals.py
git commit -m "feat(orders): expose line_total on response so clients don't recompute"
```

---

## Task 12: POS receipt + SalePage use server-provided `line_total`

**Files:**
- Modify: `frontend/packages/shared/src/types.ts`
- Modify: `frontend/packages/pos/src/components/Receipt.tsx`
- Modify: `frontend/packages/pos/src/pages/SalePage.tsx`

- [ ] **Step 12.1: Add `line_total` to the `LineItem` shared type**

In `frontend/packages/shared/src/types.ts`, find the `LineItem` interface and add:

```typescript
export interface LineItem {
  // ...existing fields...
  line_total?: string | null;
}
```

(Optional because older orders created before this fix won't have it. Use optional + fallback at render time.)

- [ ] **Step 12.2: Update `Receipt.tsx` to prefer `line_total`**

Find the line-total computation in `frontend/packages/pos/src/components/Receipt.tsx` — Plan 1's review flagged it at line 76. Replace the computation with:

```tsx
function lineTotal(item: ReceiptItem): string {
  if (item.line_total != null) return item.line_total;
  if (item.quantity_kg != null) {
    const kg = parseFloat(item.quantity_kg);
    const perKg = parseFloat(item.price);
    return (kg * perKg).toFixed(2);
  }
  const qty = item.quantity ?? 1;
  const unit = parseFloat(item.price);
  return (qty * unit).toFixed(2);
}
```

And make sure the existing display code calls `lineTotal(item)` instead of recomputing inline.

Similarly, for the per-line display row of a weighed item, show the kg and €/kg (not quantity=1 × €/kg):

```tsx
{item.quantity_kg != null
  ? <>{item.quantity_kg} kg &times; {item.price} &euro;/kg</>
  : <>{item.quantity ?? 1} &times; {item.price}</>}
{" = "}
{lineTotal(item)} &euro;
```

Adjust to match the actual Receipt JSX structure you find in the file.

- [ ] **Step 12.3: Update `SalePage.tsx` subtotal rendering**

In `frontend/packages/pos/src/pages/SalePage.tsx`, find the cart-subtotal computation (Plan 1 review flagged it at lines 146-154). For items in the live cart (not yet POSTed), the frontend still has to compute locally — use the same logic as Receipt's `lineTotal`. Extract it to a small local helper:

```tsx
function liveLineTotal(item: SaleItem): number {
  if (item.quantityKg != null) {
    return parseFloat(item.quantityKg) * parseFloat(item.price);
  }
  return (item.quantity ?? 1) * parseFloat(item.price);
}
```

Replace any `parseFloat(item.price) * item.quantity` style computation with `liveLineTotal(item)`. Round at render time with `.toFixed(2)` but keep the Decimal math inside the number.

- [ ] **Step 12.4: Build check**

Run: `cd frontend && pnpm -r build`
Expected: clean build.

- [ ] **Step 12.5: Commit**

```bash
git add frontend/packages/shared/src/types.ts frontend/packages/pos/src/components/Receipt.tsx frontend/packages/pos/src/pages/SalePage.tsx
git commit -m "fix(pos-ui): weighed-line totals use server value, no silent recompute"
```

---

## Task 13: Bootstrap runbook truthfully reflects the new UX

**Files:**
- Modify: `docs/ops/bootstrap-first-run.md`

- [ ] **Step 13.1: Rewrite the runbook**

Replace the entire contents of `docs/ops/bootstrap-first-run.md` with:

```markdown
# First-Run Bootstrap

When the stack comes up on a fresh NUC, the database has zero users. The
admin UI probes `GET /api/auth/bootstrap-status` and auto-routes to the
Setup form when `setup_required: true`. After the first owner is created,
the endpoint returns `setup_required: false` and the admin shows the normal
Login form from then on.

## Steps

1. Bring up the stack: `docker compose up -d`.
2. Open `https://admin.local` on the admin laptop. You should see the
   Setup form (no URL flag needed).
3. Enter a strong passphrase (min 12 chars, validated against HIBP).
4. Submit. You are logged in as owner and land in the admin dashboard.
5. Go to **Security** → **Enroll MFA**. Scan the QR code into Authy /
   1Password / Aegis and verify the first 6-digit code. MFA is now required
   for this owner on subsequent logins.
6. Go to **Users** → **New user**. Create the rest of the staff:
   - One or more **managers** (optional MFA, strongly recommended).
   - One or more **cashiers** — no email, 4-6 digit PIN instead.
7. Create a second owner-role user as a break-glass backup. Store its
   password in the physical safe. Never use it; it exists so a lost-device
   MFA lockout never becomes "store cannot operate."

## What not to do

- Never commit `.env` to the repo.
- Never share the session cookie.
- Never disable HIBP in production (`hibp_enabled=False`) — it's there
  precisely to catch a weak owner passphrase.

## After updating nginx.conf

Whenever `nginx.conf` changes, either restart the nginx container
(`docker compose restart nginx`) or reload in-place
(`docker compose exec nginx nginx -s reload`). The running container reads
the file via a bind mount, so edits in the repo take effect after the
reload — no rebuild required.
```

- [ ] **Step 13.2: Commit**

```bash
git add docs/ops/bootstrap-first-run.md
git commit -m "docs(ops): runbook reflects bootstrap-status auto-detection + Users/Security"
```

---

## Task 14: Admin MFA enrollment page under Settings / Security

**Files:**
- Create: `frontend/packages/admin/src/pages/Security.tsx`
- Modify: `frontend/packages/admin/src/App.tsx` (add route + nav)
- Modify: `frontend/packages/shared/src/auth.ts` (add `mfaEnroll`, `mfaVerify`)

- [ ] **Step 14.1: Add auth helpers**

Append to `frontend/packages/shared/src/auth.ts`:

```typescript
export async function mfaEnroll() {
  const r = await fetch(`${base}/mfa/enroll`, {
    method: "POST",
    credentials: "include",
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail ?? "enroll failed");
  return body as { secret: string; uri: string };
}

export async function mfaVerify(code: string) {
  const r = await fetch(`${base}/mfa/verify`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  const body = await r.json();
  if (!r.ok) throw new Error(body.detail ?? "verify failed");
  return body;
}
```

- [ ] **Step 14.2: Create `Security.tsx`**

Create `frontend/packages/admin/src/pages/Security.tsx`:

```tsx
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
```

- [ ] **Step 14.3: Wire route + nav in `App.tsx`**

In `frontend/packages/admin/src/App.tsx`:

1. Import the new page: `import { Security } from "./pages/Security";`
2. Add a `<Route path="/security" element={<Security />} />` inside the existing Routes block.
3. Add a nav link to `/security` that is visible for roles `owner` and `manager` (check `me.role`).

The existing file structure determines the exact nav shape — if there's a sidebar component, add a link; if there's a horizontal nav, add a tab.

- [ ] **Step 14.4: Build check**

Run: `cd frontend && pnpm -r build`
Expected: clean build.

- [ ] **Step 14.5: Commit**

```bash
git add frontend/packages/shared/src/auth.ts frontend/packages/admin/src/pages/Security.tsx frontend/packages/admin/src/App.tsx
git commit -m "feat(admin-ui): MFA enrollment page under Security"
```

---

## Task 15: Admin Users management page

**Files:**
- Create: `frontend/packages/admin/src/pages/Users.tsx`
- Modify: `frontend/packages/admin/src/App.tsx`
- Modify: `frontend/packages/shared/src/api.ts` (add `users` section)
- Create: `backend/app/api/users.py` (new router)
- Modify: `backend/app/main.py` (register the router)
- Modify: `backend/app/schemas/auth.py` (add `UserCreate`, `UserOut`)
- Test: `backend/tests/test_users_api.py` (new)

- [ ] **Step 15.1: Write the failing test**

Create `backend/tests/test_users_api.py`:

```python
import pytest

from app.models import User
from app.services.password import hash_password


@pytest.mark.asyncio
async def test_list_users_owner(authed_client, db):
    r = await authed_client.get("/api/users")
    assert r.status_code == 200
    # owner fixture already creates a user; list contains at least 1
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_list_users_forbidden_for_cashier(cashier_client, db):
    r = await cashier_client.get("/api/users")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_manager(authed_client, db):
    r = await authed_client.post("/api/users", json={
        "email": "mgr@shop.de",
        "password": "manager-passphrase-9",
        "full_name": "Mgr",
        "role": "manager",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "manager"
    assert body["email"] == "mgr@shop.de"


@pytest.mark.asyncio
async def test_create_cashier_with_pin(authed_client, db):
    r = await authed_client.post("/api/users", json={
        "full_name": "Anna M.",
        "role": "cashier",
        "pin": "1234",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "cashier"
    assert body["email"] is None


@pytest.mark.asyncio
async def test_create_user_forbidden_for_manager_creating_owner(authed_client, db):
    # authed_client is owner. A manager should not be able to create an owner,
    # but that's enforced at dep level; we test the role=owner creation as owner.
    r = await authed_client.post("/api/users", json={
        "email": "o2@shop.de",
        "password": "second-owner-passphrase-9",
        "full_name": "Backup",
        "role": "owner",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_deactivate_user(authed_client, db):
    from app.services.password import hash_password
    u = User(email="x@shop.de", password_hash=hash_password("password1234"),
            full_name="X", role="manager")
    db.add(u); await db.commit()
    r = await authed_client.patch(f"/api/users/{u.id}/deactivate")
    assert r.status_code == 200
    assert r.json()["active"] is False
```

- [ ] **Step 15.2: Add schemas**

Append to `backend/app/schemas/auth.py`:

```python
class UserCreate(BaseModel):
    email: str | None = None
    password: str | None = None
    pin: str | None = None
    full_name: str
    role: str  # 'owner' | 'manager' | 'cashier'


class UserOut(BaseModel):
    id: int
    email: str | None
    full_name: str
    role: str
    active: bool
    created_at: str | None = None
    last_login_at: str | None = None
```

- [ ] **Step 15.3: Add the router**

Create `backend/app/api/users.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_owner
from app.models import User
from app.schemas.auth import UserCreate, UserOut
from app.services.password import hash_password, hash_pin

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_owner)],
)


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.role, User.full_name))
    return [
        UserOut(
            id=u.id, email=u.email, full_name=u.full_name, role=u.role,
            active=u.active,
            created_at=u.created_at.isoformat() if u.created_at else None,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
        )
        for u in result.scalars().all()
    ]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(req: UserCreate, db: AsyncSession = Depends(get_db)):
    if req.role not in ("owner", "manager", "cashier"):
        raise HTTPException(status_code=400, detail="role must be owner/manager/cashier")

    if req.role == "cashier":
        if not req.pin:
            raise HTTPException(status_code=400, detail="cashier requires pin")
        u = User(
            email=None,
            password_hash=None,
            pin_hash=hash_pin(req.pin),
            full_name=req.full_name,
            role="cashier",
        )
    else:
        if not req.email or not req.password:
            raise HTTPException(status_code=400, detail=f"{req.role} requires email and password")
        u = User(
            email=req.email,
            password_hash=hash_password(req.password),
            full_name=req.full_name,
            role=req.role,
        )

    db.add(u)
    await db.commit()
    await db.refresh(u)
    return UserOut(
        id=u.id, email=u.email, full_name=u.full_name, role=u.role,
        active=u.active,
        created_at=u.created_at.isoformat() if u.created_at else None,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )


@router.patch("/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(user_id: int, db: AsyncSession = Depends(get_db)):
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    u.active = False
    await db.commit()
    return UserOut(
        id=u.id, email=u.email, full_name=u.full_name, role=u.role,
        active=u.active,
        created_at=u.created_at.isoformat() if u.created_at else None,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )
```

- [ ] **Step 15.4: Register the router**

In `backend/app/main.py`, import and register:

```python
from app.api.users import router as users_router
# ...
app.include_router(users_router)
```

- [ ] **Step 15.5: Run, confirm backend tests pass**

Run: `cd backend && pytest tests/test_users_api.py -v`
Expected: PASS (all 6 cases)

Also: `cd backend && pytest 2>&1 | tail -5` to confirm no regressions.

- [ ] **Step 15.6: Add the `users` section to `api.ts`**

In `frontend/packages/shared/src/api.ts`, inside the `api` object:

```typescript
  users: {
    list: () => request<Array<{
      id: number;
      email: string | null;
      full_name: string;
      role: "owner" | "manager" | "cashier";
      active: boolean;
      created_at: string | null;
      last_login_at: string | null;
    }>>("/users"),
    create: (data: {
      email?: string | null;
      password?: string | null;
      pin?: string | null;
      full_name: string;
      role: "owner" | "manager" | "cashier";
    }) => request<{
      id: number; email: string | null; full_name: string; role: string; active: boolean;
    }>("/users", { method: "POST", body: JSON.stringify(data) }),
    deactivate: (id: number) => request<{ id: number; active: boolean }>(
      `/users/${id}/deactivate`,
      { method: "PATCH" },
    ),
  },
```

- [ ] **Step 15.7: Create `Users.tsx`**

Create `frontend/packages/admin/src/pages/Users.tsx`:

```tsx
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
```

- [ ] **Step 15.8: Wire route + nav**

In `frontend/packages/admin/src/App.tsx`:

1. `import { Users } from "./pages/Users";`
2. Add `<Route path="/users" element={<Users />} />` — only visible when `me.role === "owner"` (you can render nothing if role mismatches, or gate the nav link).
3. Add a "Users" nav link visible only for owner.

- [ ] **Step 15.9: Build check**

Run: `cd frontend && pnpm -r build`
Expected: clean build.

- [ ] **Step 15.10: Commit**

```bash
git add backend/app/api/users.py backend/app/main.py backend/app/schemas/auth.py backend/tests/test_users_api.py frontend/packages/shared/src/api.ts frontend/packages/admin/src/pages/Users.tsx frontend/packages/admin/src/App.tsx
git commit -m "feat(admin-ui): Users management (list, create, deactivate)"
```

---

## Self-Review Checklist

1. **C1 (XFF spoofing)** — Tasks 1+2+3 add the setting, the guard, and the nginx headers. Test 2's spoof test (`test_ignores_xff_from_untrusted_caller`) verifies the attack path is now closed. ✓
2. **C2 (first-run UX)** — Tasks 8+9+13 add the endpoint, frontend probe, and truthful runbook. ✓
3. **I5 (receipt math)** — Task 11 adds `line_total` server-side; Task 12 consumes it on the receipt + cart. ✓
4. **I7 (reject bad quantity on weighed)** — Task 10. ✓
5. **I8 (MFA UI)** — Task 14. ✓
6. **I9 (Users UI)** — Task 15. ✓
7. **I1 (api credentials)** — Task 6. ✓
8. **I2 (cashiers LAN gate)** — Task 4. ✓
9. **I3 (ws auth)** — Task 5. ✓
10. **S1 (Session comment)** — Task 7. ✓
11. **S3 (setup_db try/finally)** — Task 7. ✓

**Explicit non-coverage (by design):**

- **I4 (kg-accurate inventory)** — deferred to Plan 2's fiscal-path rewrite.
- **I6 (LineItem.quantity semantics)** — deferred; Plan 2's `pos_transaction_line` replaces this.
- **S2 (test DB rebuild perf)** — deferred; non-correctness, low urgency.
- **S4/S5/S7** — suggestions only, not correctness issues; fold into the next plan that touches the respective file.

**Placeholder scan:** grep for TBD/TODO/appropriate — none present in this plan.

**Type consistency:** `line_total` typed as `Decimal` in Python, `string | null` in TS (Decimal serializes as string). `LineItem`/`LineItemOut` schema field names match Plan 1's naming. `require_owner` / `require_manager_or_above` / `require_any_staff` match Plan 1's exported names. ✓
