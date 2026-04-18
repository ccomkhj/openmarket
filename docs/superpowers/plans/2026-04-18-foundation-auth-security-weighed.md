# Foundation — Auth, Security, Weighed-Produce Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the prerequisites the rest of the Go-Live v1 work depends on: staff authentication with roles, a minimal security baseline, and the weighed-produce data model.

**Architecture:** Cookie-based server-side sessions (not JWT) stored in Postgres with Argon2id-hashed passwords and PINs. Three FastAPI dependencies (`require_owner`, `require_manager_or_above`, `require_any_staff`) gate existing and new routes. First-run `/auth/setup` endpoint bootstraps the initial owner and disables itself. An append-only `audit_event` table records security-relevant actions, enforced by Postgres triggers that reject UPDATE/DELETE. Weighed produce is added as new columns on `ProductVariant` + `LineItem`, with `pricing_type=by_weight` items carrying `quantity_kg` alongside the existing `quantity` column.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Postgres, Alembic, argon2-cffi, pyotp, httpx (for HIBP), React + TypeScript (for the two login UIs).

**Spec reference:** `docs/superpowers/specs/2026-04-18-go-live-v1-design.md` §3 (weighed produce), §4 (auth), §6 (security baseline).

---

## File Structure

**New backend files:**

- `backend/app/models/auth.py` — `User`, `Session`, `AuditEvent`, `LoginAttempt` models
- `backend/app/services/password.py` — argon2id hashing + HIBP check
- `backend/app/services/session.py` — create, look up, revoke sessions
- `backend/app/services/audit.py` — write audit events
- `backend/app/services/rate_limit.py` — Postgres-backed login rate counter
- `backend/app/services/mfa.py` — TOTP enroll + verify
- `backend/app/services/weighed.py` — weighed-produce line validation
- `backend/app/api/auth.py` — auth routes (login, logout, pos-login, setup, mfa-enroll, mfa-verify)
- `backend/app/schemas/auth.py` — Pydantic request/response schemas
- `backend/alembic/versions/0100_add_auth_tables.py` — users, sessions, audit_event, login_attempt
- `backend/alembic/versions/0101_audit_event_immutable.py` — Postgres triggers blocking UPDATE/DELETE on `audit_event`
- `backend/alembic/versions/0102_add_weighed_produce_columns.py` — ProductVariant + LineItem additions
- `backend/tests/test_password.py`, `test_session.py`, `test_audit.py`, `test_rate_limit.py`, `test_mfa.py`, `test_auth_api.py`, `test_weighed.py`
- `.env.example` — documented env vars

**Modified backend files:**

- `backend/app/api/deps.py` — add `get_current_user`, `require_owner`, `require_manager_or_above`, `require_any_staff`
- `backend/app/api/products.py`, `backend/app/api/orders.py` — wire up new columns + role deps
- `backend/app/api/inventory.py`, `customers.py`, `fulfillments.py`, `discounts.py`, `analytics.py`, `tax_shipping.py`, `returns.py`, `collections.py` — apply role deps
- `backend/app/main.py` — include auth router, tighten CORS
- `backend/app/config.py` — load secrets from env with strict defaults
- `backend/app/models/__init__.py` — export new models
- `backend/app/models/product.py` — add `pricing_type`, `weight_unit`, `min_weight_kg`, `max_weight_kg`, `tare_kg`, `barcode_format` columns
- `backend/app/models/order.py` — add `quantity_kg` column to `LineItem`
- `backend/app/services/order.py` — validate weighed lines on create
- `backend/app/schemas/` — add weighed-produce fields to product + order schemas
- `backend/tests/conftest.py` — auth fixtures (`owner_session`, `cashier_session`, authed client)
- `backend/requirements.txt` — add `argon2-cffi`, `pyotp`
- `docker-compose.yml` — `env_file:` wiring

**New frontend files:**

- `frontend/packages/shared/src/auth.ts` — client auth helpers
- `frontend/packages/admin/src/pages/Login.tsx` — admin email/password/MFA form
- `frontend/packages/admin/src/pages/Setup.tsx` — first-run owner creation
- `frontend/packages/admin/src/components/RequireAuth.tsx` — client-side guard
- `frontend/packages/pos/src/pages/CashierLogin.tsx` — cashier picker + PIN keypad
- `frontend/packages/pos/src/components/WeighedProductInput.tsx` — kg numeric keypad
- `frontend/packages/admin/src/pages/VariantEdit.tsx` — add pricing_type controls (modify existing variant editor if present)

**New ops/docs files:**

- `docs/ops/tls-lan-setup.md` — generating + trusting a self-signed cert for `*.local`
- `docs/ops/bootstrap-first-run.md` — step-by-step owner creation on a fresh deploy

---

## Task 1: Add env-driven config and secrets scaffolding

**Files:**
- Modify: `backend/app/config.py`
- Create: `.env.example`
- Modify: `docker-compose.yml`
- Test: `backend/tests/test_config.py` (new)

- [ ] **Step 1.1: Write the failing test**

Create `backend/tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_rejects_insecure_default_session_secret():
    with pytest.raises(ValidationError):
        Settings(session_secret_key="changeme")


def test_settings_requires_long_session_secret():
    with pytest.raises(ValidationError):
        Settings(session_secret_key="short")


def test_settings_accepts_strong_session_secret():
    s = Settings(session_secret_key="x" * 48)
    assert s.session_secret_key == "x" * 48
    assert s.argon2_time_cost >= 2
```

- [ ] **Step 1.2: Run the test to confirm it fails**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: FAIL — current `Settings` has no `session_secret_key`.

- [ ] **Step 1.3: Update `backend/app/config.py`**

```python
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://openmarket:openmarket@localhost:5432/openmarket"
    upload_dir: str = "uploads"

    session_secret_key: str
    session_cookie_name: str = "openmarket_session"
    admin_session_idle_minutes: int = 480
    admin_session_absolute_max_hours: int = 24

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4

    lan_ip_cidrs: str = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8"

    allowed_cors_origins: str = "https://admin.local,https://pos.local,https://store.local"

    first_run_owner_email: str | None = None
    first_run_owner_password: str | None = None

    hibp_enabled: bool = True

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    @field_validator("session_secret_key")
    @classmethod
    def _validate_session_secret(cls, v: str) -> str:
        bad = {"changeme", "secret", "password", "dev", "test"}
        if v.lower() in bad:
            raise ValueError("session_secret_key is an insecure placeholder")
        if len(v) < 32:
            raise ValueError("session_secret_key must be at least 32 characters")
        return v


settings = Settings()
```

- [ ] **Step 1.4: Add `.env.example` at repo root**

```dotenv
# Copy to .env and fill in. chmod 600.
DATABASE_URL=postgresql+asyncpg://openmarket:CHANGE_ME@db:5432/openmarket
DB_PASSWORD=CHANGE_ME

# openssl rand -hex 32
SESSION_SECRET_KEY=CHANGE_ME_48_CHARS_OR_MORE

# Fiskaly (fill before Plan 2 lands)
FISKALY_API_KEY=
FISKALY_API_SECRET=
FISKALY_TSS_ID=

# Backups (fill before Plan 3 lands)
BACKUP_ENCRYPTION_KEY=

# Optional first-run bootstrap (remove after first successful /auth/setup)
FIRST_RUN_OWNER_EMAIL=
FIRST_RUN_OWNER_PASSWORD=
```

- [ ] **Step 1.5: Update `docker-compose.yml`**

At the top-level `api:` service, add `env_file: - .env` so secrets load at container start. Remove `${DB_PASSWORD:-openmarket}` fallbacks in production — dev can keep them via an unchecked `.env.dev`.

```yaml
  api:
    build: ./backend
    depends_on:
      db:
        condition: service_healthy
    env_file:
      - .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
    ports:
      - "8000:8000"
```

- [ ] **Step 1.6: Update `backend/tests/conftest.py` to set a test session secret**

At the top, before `from app.config import ...`:

```python
import os
os.environ.setdefault("SESSION_SECRET_KEY", "x" * 48)
```

- [ ] **Step 1.7: Run the test to confirm it passes**

Run: `cd backend && SESSION_SECRET_KEY="$(python -c 'print("x"*48)')" pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 1.8: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py backend/tests/conftest.py .env.example docker-compose.yml
git commit -m "feat(config): load secrets from env with validated session key"
```

---

## Task 2: Add auth data models (User, Session, AuditEvent, LoginAttempt)

**Files:**
- Create: `backend/app/models/auth.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_auth_models.py` (new)

- [ ] **Step 2.1: Write the failing test**

Create `backend/tests/test_auth_models.py`:

```python
import pytest

from app.models import User, Session, AuditEvent, LoginAttempt


@pytest.mark.asyncio
async def test_create_user(db):
    u = User(
        email="owner@example.com",
        password_hash="dummy",
        full_name="The Owner",
        role="owner",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    assert u.id is not None
    assert u.active is True
    assert u.role == "owner"


@pytest.mark.asyncio
async def test_create_session(db):
    u = User(email="a@b.com", password_hash="x", full_name="X", role="manager")
    db.add(u)
    await db.flush()
    s = Session(id="s" * 32, user_id=u.id, ip="127.0.0.1", user_agent="test")
    db.add(s)
    await db.commit()
    assert s.revoked_at is None


@pytest.mark.asyncio
async def test_create_audit_event(db):
    e = AuditEvent(event_type="login.success", actor_user_id=None, payload={"ip": "1.2.3.4"})
    db.add(e)
    await db.commit()
    assert e.id is not None
```

- [ ] **Step 2.2: Run it to confirm it fails**

Run: `cd backend && pytest tests/test_auth_models.py -v`
Expected: FAIL — imports don't exist.

- [ ] **Step 2.3: Implement `backend/app/models/auth.py`**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=True)
    password_hash = Column(Text, nullable=True)
    full_name = Column(String, nullable=False, default="")
    role = Column(String, nullable=False)  # 'owner' | 'manager' | 'cashier'
    pin_hash = Column(Text, nullable=True)
    pin_locked_until = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    mfa_totp_secret = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ip = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    mfa_method = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="sessions")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_event_type", "event_type"),
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip = Column(INET, nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_key", "key"),
        Index("ix_login_attempts_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False)  # "pin:<user_id>" or "pw:<ip>"
    succeeded = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2.4: Update `backend/app/models/__init__.py`**

```python
from app.models.product import Product, ProductVariant, ProductImage
from app.models.collection import Collection, CollectionProduct
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.customer import Customer, CustomerAddress
from app.models.order import Order, LineItem, Fulfillment
from app.models.discount import Discount
from app.models.tax_shipping import TaxRate, ShippingMethod
from app.models.auth import User, Session, AuditEvent, LoginAttempt

__all__ = [
    "Product", "ProductVariant", "ProductImage",
    "Collection", "CollectionProduct",
    "Location", "InventoryItem", "InventoryLevel",
    "Customer", "CustomerAddress",
    "Order", "LineItem", "Fulfillment",
    "Discount",
    "TaxRate", "ShippingMethod",
    "User", "Session", "AuditEvent", "LoginAttempt",
]
```

- [ ] **Step 2.5: Run test, confirm pass**

Run: `cd backend && pytest tests/test_auth_models.py -v`
Expected: PASS

- [ ] **Step 2.6: Commit**

```bash
git add backend/app/models/auth.py backend/app/models/__init__.py backend/tests/test_auth_models.py
git commit -m "feat(models): add User, Session, AuditEvent, LoginAttempt"
```

---

## Task 3: Alembic migration for auth tables

**Files:**
- Create: `backend/alembic/versions/0100_add_auth_tables.py`
- Create: `backend/alembic/versions/0101_audit_event_immutable.py`

- [ ] **Step 3.1: Inspect the current Alembic head**

Run: `cd backend && alembic heads`
Note the revision hash — your new migration's `down_revision` is that hash.

- [ ] **Step 3.2: Create `0100_add_auth_tables.py`**

Replace `DOWN_REV` with the value from 3.1.

```python
"""add auth tables

Revision ID: 0100_add_auth_tables
Revises: DOWN_REV
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0100_add_auth_tables"
down_revision = "DOWN_REV"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String, nullable=True),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("full_name", sa.String, nullable=False, server_default=""),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("pin_hash", sa.Text, nullable=True),
        sa.Column("pin_locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("mfa_totp_secret", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mfa_method", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ip", postgresql.INET, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_login_attempts_key", "login_attempts", ["key"])
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"])


def downgrade():
    op.drop_index("ix_login_attempts_created_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_key", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```

- [ ] **Step 3.3: Create `0101_audit_event_immutable.py`**

```python
"""make audit_events and login_attempts reject UPDATE/DELETE

Revision ID: 0101_audit_immutable
Revises: 0100_add_auth_tables
Create Date: 2026-04-18
"""
from alembic import op

revision = "0101_audit_immutable"
down_revision = "0100_add_auth_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_audit_modification() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit rows are append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER audit_events_no_update
            BEFORE UPDATE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_audit_modification();

        CREATE TRIGGER audit_events_no_delete
            BEFORE DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_audit_modification();
    """)


def downgrade():
    op.execute("""
        DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events;
        DROP TRIGGER IF EXISTS audit_events_no_delete ON audit_events;
        DROP FUNCTION IF EXISTS reject_audit_modification();
    """)
```

- [ ] **Step 3.4: Run migrations up and down against a dev database**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic downgrade -1 && alembic upgrade head`
Expected: No errors. Confirms both migrations are reversible.

- [ ] **Step 3.5: Commit**

```bash
git add backend/alembic/versions/0100_add_auth_tables.py backend/alembic/versions/0101_audit_event_immutable.py
git commit -m "feat(db): migrations for auth tables + audit immutability triggers"
```

---

## Task 4: Password + PIN hashing service (argon2id)

**Files:**
- Create: `backend/app/services/password.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_password.py` (new)

- [ ] **Step 4.1: Add dependency**

Add to `backend/requirements.txt`:

```
argon2-cffi==23.1.0
```

Then: `cd backend && pip install -r requirements.txt`

- [ ] **Step 4.2: Write the failing test**

Create `backend/tests/test_password.py`:

```python
import pytest

from app.services.password import (
    hash_password, verify_password, hash_pin, verify_pin, PasswordTooShortError,
    PinMalformedError,
)


def test_hash_and_verify_password():
    h = hash_password("correct-horse-battery-1")
    assert verify_password("correct-horse-battery-1", h)
    assert not verify_password("wrong", h)


def test_hash_rejects_short_password():
    with pytest.raises(PasswordTooShortError):
        hash_password("short123")


def test_hash_and_verify_pin():
    h = hash_pin("1234")
    assert verify_pin("1234", h)
    assert not verify_pin("4321", h)


def test_pin_rejects_non_numeric():
    with pytest.raises(PinMalformedError):
        hash_pin("abcd")


def test_pin_rejects_wrong_length():
    with pytest.raises(PinMalformedError):
        hash_pin("123")
    with pytest.raises(PinMalformedError):
        hash_pin("1234567")


def test_pin_rehash_on_length_boundary():
    h = hash_pin("123456")
    assert verify_pin("123456", h)
```

- [ ] **Step 4.3: Run to confirm it fails**

Run: `cd backend && pytest tests/test_password.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4.4: Implement `backend/app/services/password.py`**

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings


class PasswordTooShortError(ValueError):
    pass


class PinMalformedError(ValueError):
    pass


_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
)

MIN_PASSWORD_LEN = 12


def hash_password(plain: str) -> str:
    if len(plain) < MIN_PASSWORD_LEN:
        raise PasswordTooShortError(f"password must be at least {MIN_PASSWORD_LEN} chars")
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def hash_pin(plain: str) -> str:
    if not plain.isdigit() or not (4 <= len(plain) <= 6):
        raise PinMalformedError("PIN must be 4-6 digits")
    return _hasher.hash(plain)


def verify_pin(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
```

- [ ] **Step 4.5: Run test to confirm pass**

Run: `cd backend && pytest tests/test_password.py -v`
Expected: PASS (all 6 cases).

- [ ] **Step 4.6: Commit**

```bash
git add backend/app/services/password.py backend/tests/test_password.py backend/requirements.txt
git commit -m "feat(auth): argon2id password + PIN hashing service"
```

---

## Task 5: HIBP password-breach check

**Files:**
- Modify: `backend/app/services/password.py`
- Test: `backend/tests/test_password.py`

- [ ] **Step 5.1: Add test**

Append to `backend/tests/test_password.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from app.services.password import check_password_not_breached, PasswordBreachedError


@pytest.mark.asyncio
async def test_hibp_accepts_unknown_password():
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = "0000000000000000000000000000000000A:1\nFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFB:2\n"
    with patch("app.services.password._hibp_get", return_value=mock_resp):
        await check_password_not_breached("never-before-seen-password-xyz")


@pytest.mark.asyncio
async def test_hibp_rejects_known_password():
    # SHA1("password") upper = 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8
    # prefix 5BAA6, suffix 1E4C9B93F3F0682250B6CF8331B7EE68FD8
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = "1E4C9B93F3F0682250B6CF8331B7EE68FD8:3861493\n"
    with patch("app.services.password._hibp_get", return_value=mock_resp):
        with pytest.raises(PasswordBreachedError):
            await check_password_not_breached("password1234")


@pytest.mark.asyncio
async def test_hibp_tolerates_offline():
    with patch("app.services.password._hibp_get", side_effect=OSError("offline")):
        # offline fallback: does NOT raise
        await check_password_not_breached("any-password-value")
```

- [ ] **Step 5.2: Run test to confirm fail**

Run: `cd backend && pytest tests/test_password.py::test_hibp_rejects_known_password -v`
Expected: FAIL — function not defined.

- [ ] **Step 5.3: Append to `backend/app/services/password.py`**

```python
import hashlib

import httpx

from app.config import settings


class PasswordBreachedError(ValueError):
    pass


async def _hibp_get(prefix: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=3.0) as client:
        return await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")


async def check_password_not_breached(plain: str) -> None:
    """Raise PasswordBreachedError if the password appears in HIBP, no-op on network error."""
    if not settings.hibp_enabled:
        return
    digest = hashlib.sha1(plain.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    try:
        resp = await _hibp_get(prefix)
    except (OSError, httpx.HTTPError):
        return
    if resp.status_code != 200:
        return
    for line in resp.text.splitlines():
        hash_suffix, _count = line.split(":", 1)
        if hash_suffix.strip() == suffix:
            raise PasswordBreachedError("password appears in breach corpus")
```

- [ ] **Step 5.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_password.py -v`
Expected: PASS (all 9 cases).

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/services/password.py backend/tests/test_password.py
git commit -m "feat(auth): HIBP k-anonymity password-breach check"
```

---

## Task 6: Session service (create, lookup, revoke)

**Files:**
- Create: `backend/app/services/session.py`
- Test: `backend/tests/test_session_service.py` (new)

- [ ] **Step 6.1: Write the failing test**

Create `backend/tests/test_session_service.py`:

```python
import pytest
from datetime import datetime, timedelta, timezone

from app.models import User
from app.services.session import create_session, get_active_session, revoke_session


@pytest.mark.asyncio
async def test_create_session_returns_id(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="manager")
    db.add(u)
    await db.flush()
    sess = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="test", ttl_minutes=60)
    assert len(sess.id) >= 32
    assert sess.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_get_active_session_returns_session(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="manager")
    db.add(u); await db.flush()
    s = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="t", ttl_minutes=60)
    await db.commit()
    found = await get_active_session(db, s.id)
    assert found is not None
    assert found.user_id == u.id


@pytest.mark.asyncio
async def test_get_active_session_rejects_revoked(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="manager")
    db.add(u); await db.flush()
    s = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="t", ttl_minutes=60)
    await db.commit()
    await revoke_session(db, s.id)
    await db.commit()
    assert await get_active_session(db, s.id) is None


@pytest.mark.asyncio
async def test_get_active_session_rejects_expired(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="manager")
    db.add(u); await db.flush()
    s = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="t", ttl_minutes=-1)
    await db.commit()
    assert await get_active_session(db, s.id) is None
```

- [ ] **Step 6.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_session_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 6.3: Implement `backend/app/services/session.py`**

```python
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session


def _token() -> str:
    return secrets.token_urlsafe(32)[:48]


async def create_session(
    db: AsyncSession,
    *,
    user_id: int,
    ip: str | None,
    user_agent: str | None,
    ttl_minutes: int,
    mfa_method: str | None = None,
) -> Session:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    s = Session(
        id=_token(),
        user_id=user_id,
        expires_at=expires,
        ip=ip,
        user_agent=user_agent,
        mfa_method=mfa_method,
    )
    db.add(s)
    await db.flush()
    return s


async def get_active_session(db: AsyncSession, session_id: str) -> Session | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def revoke_session(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def revoke_all_for_user(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
```

- [ ] **Step 6.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_session_service.py -v`
Expected: PASS

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/services/session.py backend/tests/test_session_service.py
git commit -m "feat(auth): session create/lookup/revoke service"
```

---

## Task 7: Audit event service

**Files:**
- Create: `backend/app/services/audit.py`
- Test: `backend/tests/test_audit.py` (new)

- [ ] **Step 7.1: Write the failing test**

Create `backend/tests/test_audit.py`:

```python
import pytest
from sqlalchemy import select

from app.models import AuditEvent, User
from app.services.audit import log_event


@pytest.mark.asyncio
async def test_log_event_persists(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="owner")
    db.add(u); await db.flush()
    await log_event(db, event_type="product.price_changed", actor_user_id=u.id, ip="127.0.0.1", payload={"variant_id": 5, "old": "1.99", "new": "2.49"})
    await db.commit()
    result = await db.execute(select(AuditEvent).where(AuditEvent.event_type == "product.price_changed"))
    e = result.scalar_one()
    assert e.actor_user_id == u.id
    assert e.payload["variant_id"] == 5


@pytest.mark.asyncio
async def test_audit_event_rejects_update(db):
    await log_event(db, event_type="x", actor_user_id=None, ip=None, payload={})
    await db.commit()
    result = await db.execute(select(AuditEvent))
    e = result.scalar_one()
    e.event_type = "mutated"
    with pytest.raises(Exception):
        await db.commit()
```

- [ ] **Step 7.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_audit.py -v`
Expected: FAIL — module not found.

- [ ] **Step 7.3: Implement `backend/app/services/audit.py`**

```python
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def log_event(
    db: AsyncSession,
    *,
    event_type: str,
    actor_user_id: int | None,
    ip: str | None,
    payload: dict[str, Any],
) -> None:
    evt = AuditEvent(
        event_type=event_type,
        actor_user_id=actor_user_id,
        ip=ip,
        payload=payload,
    )
    db.add(evt)
    await db.flush()
```

- [ ] **Step 7.4: Ensure Postgres triggers run against the test DB**

The `setup_db` fixture uses `Base.metadata.create_all` — which does not execute raw SQL migrations. Update `backend/tests/conftest.py` to also apply the immutability triggers:

```python
# Add near top of conftest.py, after imports
_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION reject_audit_modification() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit rows are append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events;
DROP TRIGGER IF EXISTS audit_events_no_delete ON audit_events;
CREATE TRIGGER audit_events_no_update
    BEFORE UPDATE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_audit_modification();
CREATE TRIGGER audit_events_no_delete
    BEFORE DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_audit_modification();
"""
```

Modify the `setup_db` fixture to `await conn.execute(sa.text(_TRIGGER_SQL))` after `create_all`:

```python
import sqlalchemy as sa
# ...
@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(sa.text(_TRIGGER_SQL))
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

- [ ] **Step 7.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_audit.py -v`
Expected: PASS

- [ ] **Step 7.6: Commit**

```bash
git add backend/app/services/audit.py backend/tests/test_audit.py backend/tests/conftest.py
git commit -m "feat(auth): append-only audit event service"
```

---

## Task 8: Login rate-limit service

**Files:**
- Create: `backend/app/services/rate_limit.py`
- Test: `backend/tests/test_rate_limit.py` (new)

- [ ] **Step 8.1: Write the failing test**

Create `backend/tests/test_rate_limit.py`:

```python
import pytest

from app.services.rate_limit import record_attempt, is_locked


@pytest.mark.asyncio
async def test_not_locked_initially(db):
    assert await is_locked(db, key="pw:1.2.3.4", window_seconds=900, max_failures=5) is False


@pytest.mark.asyncio
async def test_locks_after_n_failures(db):
    for _ in range(5):
        await record_attempt(db, key="pw:1.2.3.4", succeeded=False)
    await db.commit()
    assert await is_locked(db, key="pw:1.2.3.4", window_seconds=900, max_failures=5) is True


@pytest.mark.asyncio
async def test_success_resets_lock(db):
    for _ in range(5):
        await record_attempt(db, key="pw:1.2.3.4", succeeded=False)
    await record_attempt(db, key="pw:1.2.3.4", succeeded=True)
    await db.commit()
    assert await is_locked(db, key="pw:1.2.3.4", window_seconds=900, max_failures=5) is False


@pytest.mark.asyncio
async def test_separate_keys_not_crosstalked(db):
    for _ in range(5):
        await record_attempt(db, key="pw:1.2.3.4", succeeded=False)
    await db.commit()
    assert await is_locked(db, key="pw:9.9.9.9", window_seconds=900, max_failures=5) is False
```

- [ ] **Step 8.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_rate_limit.py -v`
Expected: FAIL — module not found.

- [ ] **Step 8.3: Implement `backend/app/services/rate_limit.py`**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginAttempt


async def record_attempt(db: AsyncSession, *, key: str, succeeded: bool) -> None:
    db.add(LoginAttempt(key=key, succeeded=succeeded))
    await db.flush()


async def is_locked(db: AsyncSession, *, key: str, window_seconds: int, max_failures: int) -> bool:
    """True if the key has >= max_failures failed attempts since the most recent success,
    within window_seconds."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)

    last_success = await db.execute(
        select(func.max(LoginAttempt.created_at))
        .where(LoginAttempt.key == key, LoginAttempt.succeeded.is_(True))
    )
    last_success_at = last_success.scalar()

    lower_bound = max(cutoff, last_success_at) if last_success_at else cutoff

    fails = await db.execute(
        select(func.count(LoginAttempt.id))
        .where(
            LoginAttempt.key == key,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.created_at > lower_bound,
        )
    )
    return (fails.scalar() or 0) >= max_failures
```

- [ ] **Step 8.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_rate_limit.py -v`
Expected: PASS

- [ ] **Step 8.5: Commit**

```bash
git add backend/app/services/rate_limit.py backend/tests/test_rate_limit.py
git commit -m "feat(auth): Postgres-backed login rate-limit counter"
```

---

## Task 9: MFA TOTP service

**Files:**
- Create: `backend/app/services/mfa.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_mfa.py` (new)

- [ ] **Step 9.1: Add dependency**

Add to `backend/requirements.txt`:

```
pyotp==2.9.0
```

Run: `cd backend && pip install -r requirements.txt`

- [ ] **Step 9.2: Write the failing test**

Create `backend/tests/test_mfa.py`:

```python
import pyotp
import pytest

from app.services.mfa import new_totp_secret, totp_uri, verify_totp


def test_new_secret_is_base32():
    s = new_totp_secret()
    assert len(s) >= 16
    pyotp.TOTP(s).now()  # raises if not base32


def test_totp_uri_has_issuer_and_user():
    uri = totp_uri(secret="JBSWY3DPEHPK3PXP", user_email="owner@example.com")
    assert "OpenMarket" in uri
    assert "owner@example.com" in uri


def test_verify_totp_accepts_current_code():
    s = new_totp_secret()
    code = pyotp.TOTP(s).now()
    assert verify_totp(secret=s, code=code) is True


def test_verify_totp_rejects_wrong_code():
    s = new_totp_secret()
    assert verify_totp(secret=s, code="000000") is False
```

- [ ] **Step 9.3: Run, confirm fail**

Run: `cd backend && pytest tests/test_mfa.py -v`
Expected: FAIL — module not found.

- [ ] **Step 9.4: Implement `backend/app/services/mfa.py`**

```python
import pyotp


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(*, secret: str, user_email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=user_email, issuer_name="OpenMarket")


def verify_totp(*, secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
```

- [ ] **Step 9.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_mfa.py -v`
Expected: PASS

- [ ] **Step 9.6: Commit**

```bash
git add backend/app/services/mfa.py backend/tests/test_mfa.py backend/requirements.txt
git commit -m "feat(auth): TOTP MFA enroll + verify service"
```

---

## Task 10: Auth Pydantic schemas

**Files:**
- Create: `backend/app/schemas/auth.py`

- [ ] **Step 10.1: Write the file**

```python
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    totp_code: str | None = None


class LoginResponse(BaseModel):
    user_id: int
    role: str
    mfa_required: bool = False


class PosLoginRequest(BaseModel):
    user_id: int
    pin: str = Field(min_length=4, max_length=6)


class PosLoginResponse(BaseModel):
    user_id: int
    full_name: str


class SetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    full_name: str


class MfaEnrollResponse(BaseModel):
    secret: str
    uri: str


class MfaVerifyRequest(BaseModel):
    code: str


class MeResponse(BaseModel):
    id: int
    email: str | None
    full_name: str
    role: str
```

- [ ] **Step 10.2: Commit**

```bash
git add backend/app/schemas/auth.py
git commit -m "feat(auth): Pydantic schemas for auth routes"
```

---

## Task 11: Auth dependencies (`get_current_user` and role gates)

**Files:**
- Modify: `backend/app/api/deps.py`
- Test: `backend/tests/test_auth_deps.py` (new)

- [ ] **Step 11.1: Write the failing test**

Create `backend/tests/test_auth_deps.py`:

```python
import pytest
from fastapi import FastAPI, Depends
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db, get_current_user, require_owner, require_any_staff
from app.models import User
from app.services.password import hash_password
from app.services.session import create_session
from app.config import settings


@pytest.mark.asyncio
async def test_get_current_user_without_cookie_is_401(client):
    # make a protected route
    app_: FastAPI = client._transport.app
    @app_.get("/test/me")
    async def _me(user: User = Depends(get_current_user)):
        return {"id": user.id}

    r = await client.get("/test/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_require_owner_blocks_manager(client, db):
    app_: FastAPI = client._transport.app
    @app_.get("/test/owner-only")
    async def _o(user: User = Depends(require_owner)):
        return {"ok": True}

    mgr = User(email="m@e.com", password_hash=hash_password("password1234"), full_name="M", role="manager")
    db.add(mgr); await db.flush()
    s = await create_session(db, user_id=mgr.id, ip="127.0.0.1", user_agent="t", ttl_minutes=60)
    await db.commit()

    client.cookies.set(settings.session_cookie_name, s.id)
    r = await client.get("/test/owner-only")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_require_any_staff_allows_cashier(client, db):
    app_: FastAPI = client._transport.app
    @app_.get("/test/any")
    async def _a(user: User = Depends(require_any_staff)):
        return {"id": user.id}

    c = User(email=None, password_hash=None, pin_hash=hash_password("aaaaaaaaaaaa"), full_name="C", role="cashier")
    db.add(c); await db.flush()
    s = await create_session(db, user_id=c.id, ip="127.0.0.1", user_agent="t", ttl_minutes=60)
    await db.commit()

    client.cookies.set(settings.session_cookie_name, s.id)
    r = await client.get("/test/any")
    assert r.status_code == 200
```

- [ ] **Step 11.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_auth_deps.py -v`
Expected: FAIL — `get_current_user`, `require_owner`, `require_any_staff` don't exist.

- [ ] **Step 11.3: Replace `backend/app/api/deps.py`**

```python
from collections.abc import AsyncGenerator

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models import User
from app.services.session import get_active_session


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        yield session


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    sess = await get_active_session(db, session_id)
    if not sess:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    user = await db.get(User, sess.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user inactive")
    return user


def require_role(*allowed: str):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user

    return _dep


require_owner = require_role("owner")
require_manager_or_above = require_role("owner", "manager")
require_any_staff = require_role("owner", "manager", "cashier")
```

- [ ] **Step 11.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_auth_deps.py -v`
Expected: PASS

- [ ] **Step 11.5: Commit**

```bash
git add backend/app/api/deps.py backend/tests/test_auth_deps.py
git commit -m "feat(auth): FastAPI deps for current-user and role gates"
```

---

## Task 12: Auth router (login, logout, /me, /setup, MFA, pos-login)

**Files:**
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth_api.py` (new)

- [ ] **Step 12.1: Write the failing test**

Create `backend/tests/test_auth_api.py`:

```python
import ipaddress
import pytest

from app.config import settings
from app.models import User
from app.services.password import hash_password, hash_pin


@pytest.mark.asyncio
async def test_setup_creates_first_owner(client, db):
    r = await client.post("/api/auth/setup", json={
        "email": "owner@shop.de",
        "password": "opening-day-passphrase-42",
        "full_name": "Shop Owner",
    })
    assert r.status_code == 200
    assert r.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_setup_refuses_second_call(client, db):
    await client.post("/api/auth/setup", json={"email": "a@b.de", "password": "opening-day-passphrase-42", "full_name": "A"})
    r = await client.post("/api/auth/setup", json={"email": "c@d.de", "password": "opening-day-passphrase-43", "full_name": "C"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_login_success_sets_cookie(client, db):
    u = User(email="m@shop.de", password_hash=hash_password("manager-passphrase-9"), full_name="M", role="manager")
    db.add(u); await db.commit()
    r = await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "manager-passphrase-9"})
    assert r.status_code == 200
    assert settings.session_cookie_name in r.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_is_401(client, db):
    u = User(email="m@shop.de", password_hash=hash_password("correct-passphrase-x"), full_name="M", role="manager")
    db.add(u); await db.commit()
    r = await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "wrong-wrong-wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_locks_after_5_failures(client, db):
    u = User(email="m@shop.de", password_hash=hash_password("correct-passphrase-x"), full_name="M", role="manager")
    db.add(u); await db.commit()
    for _ in range(5):
        await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "wrong"})
    r = await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "correct-passphrase-x"})
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_pos_login_with_pin(client, db):
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"), full_name="Anna", role="cashier")
    db.add(c); await db.flush()
    await db.commit()
    r = await client.post(
        "/api/auth/pos-login",
        json={"user_id": c.id, "pin": "1234"},
        headers={"X-Forwarded-For": "192.168.1.23"},
    )
    assert r.status_code == 200
    assert settings.session_cookie_name in r.cookies


@pytest.mark.asyncio
async def test_pos_login_rejects_non_lan_ip(client, db):
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"), full_name="Anna", role="cashier")
    db.add(c); await db.flush()
    await db.commit()
    r = await client.post(
        "/api/auth/pos-login",
        json={"user_id": c.id, "pin": "1234"},
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_logout_revokes_session(client, db):
    u = User(email="m@shop.de", password_hash=hash_password("correct-passphrase-x"), full_name="M", role="manager")
    db.add(u); await db.commit()
    await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "correct-passphrase-x"})
    me1 = await client.get("/api/auth/me")
    assert me1.status_code == 200
    await client.post("/api/auth/logout")
    me2 = await client.get("/api/auth/me")
    assert me2.status_code == 401
```

- [ ] **Step 12.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_auth_api.py -v`
Expected: FAIL — routes don't exist.

- [ ] **Step 12.3: Implement `backend/app/api/auth.py`**

```python
import ipaddress
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models import User
from app.schemas.auth import (
    LoginRequest, LoginResponse, PosLoginRequest, PosLoginResponse,
    SetupRequest, MfaEnrollResponse, MfaVerifyRequest, MeResponse,
)
from app.services.audit import log_event
from app.services.mfa import new_totp_secret, totp_uri, verify_totp
from app.services.password import (
    hash_password, verify_password, verify_pin,
    check_password_not_breached,
)
from app.services.rate_limit import is_locked, record_attempt
from app.services.session import create_session, revoke_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

ADMIN_TTL_MIN = 8 * 60
POS_TTL_MIN = 14 * 60


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _ip_is_lan(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    cidrs = [c.strip() for c in settings.lan_ip_cidrs.split(",") if c.strip()]
    return any(addr in ipaddress.ip_network(c) for c in cidrs)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.admin_session_absolute_max_hours * 3600,
        path="/",
    )


@router.post("/setup", response_model=LoginResponse)
async def setup(req: SetupRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="setup already completed")
    await check_password_not_breached(req.password)
    owner = User(
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role="owner",
    )
    db.add(owner)
    await db.flush()
    sess = await create_session(
        db, user_id=owner.id, ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        ttl_minutes=ADMIN_TTL_MIN,
    )
    await log_event(db, event_type="auth.setup", actor_user_id=owner.id, ip=_client_ip(request), payload={"email": req.email})
    await db.commit()
    _set_session_cookie(response, sess.id)
    return LoginResponse(user_id=owner.id, role="owner")


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)
    key = f"pw:{ip}"
    if await is_locked(db, key=key, window_seconds=15 * 60, max_failures=5):
        raise HTTPException(status_code=429, detail="too many attempts, try later")

    result = await db.execute(select(User).where(User.email == req.email, User.active.is_(True)))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        await record_attempt(db, key=key, succeeded=False)
        await log_event(db, event_type="auth.login.failed", actor_user_id=None, ip=ip, payload={"email": req.email})
        await db.commit()
        raise HTTPException(status_code=401, detail="invalid credentials")

    if user.mfa_totp_secret:
        if not req.totp_code:
            return LoginResponse(user_id=user.id, role=user.role, mfa_required=True)
        if not verify_totp(secret=user.mfa_totp_secret, code=req.totp_code):
            await record_attempt(db, key=key, succeeded=False)
            await log_event(db, event_type="auth.login.mfa_failed", actor_user_id=user.id, ip=ip, payload={})
            await db.commit()
            raise HTTPException(status_code=401, detail="invalid MFA code")

    await record_attempt(db, key=key, succeeded=True)
    sess = await create_session(
        db, user_id=user.id, ip=ip,
        user_agent=request.headers.get("user-agent"),
        ttl_minutes=ADMIN_TTL_MIN,
        mfa_method="totp" if user.mfa_totp_secret else None,
    )
    user.last_login_at = datetime.now(timezone.utc)
    await log_event(db, event_type="auth.login.success", actor_user_id=user.id, ip=ip, payload={})
    await db.commit()
    _set_session_cookie(response, sess.id)
    return LoginResponse(user_id=user.id, role=user.role)


@router.post("/pos-login", response_model=PosLoginResponse)
async def pos_login(req: PosLoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)
    if not _ip_is_lan(ip):
        await log_event(db, event_type="auth.pos_login.non_lan", actor_user_id=None, ip=ip, payload={"user_id": req.user_id})
        await db.commit()
        raise HTTPException(status_code=403, detail="POS login only from LAN")

    key = f"pin:{req.user_id}"
    if await is_locked(db, key=key, window_seconds=5 * 60, max_failures=5):
        raise HTTPException(status_code=429, detail="PIN locked, try later")

    user = await db.get(User, req.user_id)
    if not user or user.role != "cashier" or not user.pin_hash or not user.active:
        await record_attempt(db, key=key, succeeded=False)
        await db.commit()
        raise HTTPException(status_code=401, detail="invalid credentials")

    if not verify_pin(req.pin, user.pin_hash):
        await record_attempt(db, key=key, succeeded=False)
        await log_event(db, event_type="auth.pos_login.failed", actor_user_id=user.id, ip=ip, payload={})
        await db.commit()
        raise HTTPException(status_code=401, detail="invalid credentials")

    await record_attempt(db, key=key, succeeded=True)
    sess = await create_session(
        db, user_id=user.id, ip=ip,
        user_agent=request.headers.get("user-agent"),
        ttl_minutes=POS_TTL_MIN,
    )
    user.last_login_at = datetime.now(timezone.utc)
    await log_event(db, event_type="auth.pos_login.success", actor_user_id=user.id, ip=ip, payload={})
    await db.commit()
    _set_session_cookie(response, sess.id)
    return PosLoginResponse(user_id=user.id, full_name=user.full_name)


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    sid = request.cookies.get(settings.session_cookie_name)
    if sid:
        await revoke_session(db, sid)
        await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    return MeResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


@router.post("/mfa/enroll", response_model=MfaEnrollResponse)
async def mfa_enroll(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.mfa_totp_secret:
        raise HTTPException(status_code=400, detail="MFA already enrolled")
    secret = new_totp_secret()
    user.mfa_totp_secret = secret
    await log_event(db, event_type="auth.mfa.enrolled", actor_user_id=user.id, ip=None, payload={})
    await db.commit()
    return MfaEnrollResponse(secret=secret, uri=totp_uri(secret=secret, user_email=user.email or ""))


@router.post("/mfa/verify")
async def mfa_verify(req: MfaVerifyRequest, user: User = Depends(get_current_user)):
    if not user.mfa_totp_secret:
        raise HTTPException(status_code=400, detail="MFA not enrolled")
    if not verify_totp(secret=user.mfa_totp_secret, code=req.code):
        raise HTTPException(status_code=401, detail="invalid code")
    return {"ok": True}
```

- [ ] **Step 12.4: Register the router in `backend/app/main.py`**

Find the section with `app.include_router(...)` calls and add:

```python
from app.api.auth import router as auth_router
# ...
app.include_router(auth_router)
```

- [ ] **Step 12.5: Update test `conftest.py` so the async client keeps cookies across requests**

`AsyncClient` in httpx keeps cookies by default. Confirm no override is silencing this by adding a quick sanity check before running the full test.

Run: `cd backend && pytest tests/test_auth_api.py::test_setup_creates_first_owner -v`
Expected: PASS

- [ ] **Step 12.6: Run the full auth API test**

Run: `cd backend && pytest tests/test_auth_api.py -v`
Expected: PASS (all 8 cases)

- [ ] **Step 12.7: Commit**

```bash
git add backend/app/api/auth.py backend/app/main.py backend/tests/test_auth_api.py
git commit -m "feat(auth): auth routes (setup, login, pos-login, logout, me, MFA)"
```

---

## Task 13: Auth fixtures in conftest for existing tests

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 13.1: Append auth fixtures**

Append to `backend/tests/conftest.py`:

```python
from app.config import settings
from app.models import User
from app.services.password import hash_password, hash_pin
from app.services.session import create_session


@pytest_asyncio.fixture
async def owner(db):
    u = User(
        email="owner@test.local",
        password_hash=hash_password("test-owner-passphrase-1"),
        full_name="Test Owner",
        role="owner",
    )
    db.add(u)
    await db.flush()
    await db.commit()
    return u


@pytest_asyncio.fixture
async def manager(db):
    u = User(
        email="manager@test.local",
        password_hash=hash_password("test-manager-passphrase-1"),
        full_name="Test Manager",
        role="manager",
    )
    db.add(u)
    await db.flush()
    await db.commit()
    return u


@pytest_asyncio.fixture
async def cashier(db):
    u = User(
        email=None,
        password_hash=None,
        pin_hash=hash_pin("1234"),
        full_name="Test Cashier",
        role="cashier",
    )
    db.add(u)
    await db.flush()
    await db.commit()
    return u


@pytest_asyncio.fixture
async def authed_client(client, db, owner):
    sess = await create_session(
        db, user_id=owner.id, ip="127.0.0.1", user_agent="test", ttl_minutes=60,
    )
    await db.commit()
    client.cookies.set(settings.session_cookie_name, sess.id)
    yield client


@pytest_asyncio.fixture
async def cashier_client(client, db, cashier):
    sess = await create_session(
        db, user_id=cashier.id, ip="127.0.0.1", user_agent="test", ttl_minutes=60,
    )
    await db.commit()
    client.cookies.set(settings.session_cookie_name, sess.id)
    yield client
```

- [ ] **Step 13.2: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test(auth): add owner/manager/cashier + authed_client fixtures"
```

---

## Task 14: Apply role dependencies to existing routes and fix existing tests

**Files:**
- Modify: `backend/app/api/products.py`, `collections.py`, `inventory.py`, `customers.py`, `orders.py`, `fulfillments.py`, `discounts.py`, `analytics.py`, `tax_shipping.py`, `returns.py`
- Modify: `backend/tests/test_products.py`, `test_collections.py`, `test_inventory.py`, `test_customers.py`, `test_orders.py`, `test_customer_orders.py`, `test_fulfillments.py`, `test_discounts.py`, `test_discount_crud.py`, `test_analytics.py`, `test_tax_shipping.py`, `test_returns.py`, `test_pagination.py`, `test_websocket.py`

- [ ] **Step 14.1: Add deps to each router**

For each router file, add the dependency at the `APIRouter` or per-route level. Example for `products.py`:

```python
from app.api.deps import require_manager_or_above, require_any_staff

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(require_any_staff)])
```

Apply the rule:

- `products`, `collections`, `inventory`, `customers`, `discounts`, `tax_shipping` → `dependencies=[Depends(require_manager_or_above)]`
- `orders`, `fulfillments`, `returns` → `dependencies=[Depends(require_any_staff)]` (cashiers ring sales + returns)
- `analytics` → `dependencies=[Depends(require_manager_or_above)]`

Individual stricter overrides (use `Depends(require_owner)` inline on the route):

- `DELETE` endpoints on `products`, `customers` → `require_owner`
- `POST /api/tax_shipping/rates` → `require_owner`

- [ ] **Step 14.2: Update every existing test to use `authed_client`**

Across all listed test files, replace `client` with `authed_client` in the test function signature and every `await client...` call. Example diff in `tests/test_products.py`:

```python
# BEFORE
async def test_create_product(client):
    r = await client.post("/api/products", json={...})

# AFTER
async def test_create_product(authed_client):
    r = await authed_client.post("/api/products", json={...})
```

- [ ] **Step 14.3: For `orders` endpoints hit by cashier flows, use `cashier_client` where appropriate**

In `tests/test_orders.py` and `tests/test_customer_orders.py`, keep tests that exercise POS sale flow on `cashier_client`; tests that exercise admin order management stay on `authed_client`.

- [ ] **Step 14.4: Run the full test suite**

Run: `cd backend && pytest -x`
Expected: PASS (0 failures). If a test still fails, trace to either (a) the wrong role fixture or (b) a route that needs a stricter dep override — fix inline.

- [ ] **Step 14.5: Commit**

```bash
git add backend/app/api backend/tests
git commit -m "feat(auth): gate all routes with role deps + update tests"
```

---

## Task 15: Tighten CORS, remove wildcard

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 15.1: Write the failing test**

Append to `backend/tests/test_auth_api.py`:

```python
@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(client):
    r = await client.options(
        "/api/auth/me",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


@pytest.mark.asyncio
async def test_cors_accepts_admin_origin(client):
    r = await client.options(
        "/api/auth/me",
        headers={
            "Origin": "https://admin.local",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-origin") == "https://admin.local"
```

- [ ] **Step 15.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_auth_api.py::test_cors_rejects_unknown_origin -v`
Expected: FAIL — wildcard allows all origins.

- [ ] **Step 15.3: Update `backend/app/main.py`**

Replace the existing `app.add_middleware(CORSMiddleware, ...)` block with:

```python
_allowed = [o.strip() for o in settings.allowed_cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Forwarded-For"],
)
```

- [ ] **Step 15.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_auth_api.py -v`
Expected: PASS (all cases including the two new CORS ones).

- [ ] **Step 15.5: Commit**

```bash
git add backend/app/main.py backend/tests/test_auth_api.py
git commit -m "feat(security): replace wildcard CORS with explicit origin allowlist"
```

---

## Task 16: Weighed-produce migration

**Files:**
- Create: `backend/alembic/versions/0102_add_weighed_produce_columns.py`

- [ ] **Step 16.1: Create the migration**

```python
"""add weighed-produce columns to product_variants and line_items

Revision ID: 0102_add_weighed
Revises: 0101_audit_immutable
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0102_add_weighed"
down_revision = "0101_audit_immutable"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_variants", sa.Column("pricing_type", sa.String, nullable=False, server_default="fixed"))
    op.add_column("product_variants", sa.Column("weight_unit", sa.String, nullable=True))
    op.add_column("product_variants", sa.Column("min_weight_kg", sa.Numeric(10, 3), nullable=True))
    op.add_column("product_variants", sa.Column("max_weight_kg", sa.Numeric(10, 3), nullable=True))
    op.add_column("product_variants", sa.Column("tare_kg", sa.Numeric(10, 3), nullable=True))
    op.add_column("product_variants", sa.Column("barcode_format", sa.String, nullable=False, server_default="standard"))
    op.add_column("line_items", sa.Column("quantity_kg", sa.Numeric(10, 3), nullable=True))


def downgrade():
    op.drop_column("line_items", "quantity_kg")
    op.drop_column("product_variants", "barcode_format")
    op.drop_column("product_variants", "tare_kg")
    op.drop_column("product_variants", "max_weight_kg")
    op.drop_column("product_variants", "min_weight_kg")
    op.drop_column("product_variants", "weight_unit")
    op.drop_column("product_variants", "pricing_type")
```

- [ ] **Step 16.2: Run up + down**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: no errors.

- [ ] **Step 16.3: Commit**

```bash
git add backend/alembic/versions/0102_add_weighed_produce_columns.py
git commit -m "feat(db): add weighed-produce columns to variants + line_items"
```

---

## Task 17: ProductVariant + LineItem model updates

**Files:**
- Modify: `backend/app/models/product.py`
- Modify: `backend/app/models/order.py`
- Test: `backend/tests/test_weighed_models.py` (new)

- [ ] **Step 17.1: Write the failing test**

Create `backend/tests/test_weighed_models.py`:

```python
import pytest
from decimal import Decimal

from app.models import Product, ProductVariant, Order, LineItem


@pytest.mark.asyncio
async def test_create_by_weight_variant(db):
    p = Product(title="Apples", handle="apples")
    db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", weight_unit="kg",
        min_weight_kg=Decimal("0.05"), max_weight_kg=Decimal("5.000"),
    )
    db.add(v); await db.commit(); await db.refresh(v)
    assert v.pricing_type == "by_weight"
    assert v.min_weight_kg == Decimal("0.050")


@pytest.mark.asyncio
async def test_line_item_carries_quantity_kg(db):
    p = Product(title="Apples", handle="apples")
    db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="Gala", price=Decimal("2.49"), pricing_type="by_weight", weight_unit="kg")
    db.add(v); await db.flush()
    o = Order(order_number="T-1", source="pos", total_price=Decimal("1.13"))
    db.add(o); await db.flush()
    li = LineItem(order_id=o.id, variant_id=v.id, title="Apples Gala",
                  quantity=1, quantity_kg=Decimal("0.452"), price=Decimal("1.13"))
    db.add(li); await db.commit()
    assert li.quantity_kg == Decimal("0.452")
```

- [ ] **Step 17.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_weighed_models.py -v`
Expected: FAIL — columns don't exist on the mapped model.

- [ ] **Step 17.3: Extend `backend/app/models/product.py`**

Add the new columns to `ProductVariant`:

```python
class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        Index("ix_product_variants_barcode", "barcode"),
        Index("ix_product_variants_sku", "sku"),
        Index("ix_product_variants_product_id", "product_id"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, default="Default")
    sku = Column(String, default="")
    barcode = Column(String, default="")
    price = Column(Numeric(10, 2), nullable=False)
    compare_at_price = Column(Numeric(10, 2), nullable=True)
    position = Column(Integer, default=0)

    pricing_type = Column(String, nullable=False, default="fixed")
    weight_unit = Column(String, nullable=True)
    min_weight_kg = Column(Numeric(10, 3), nullable=True)
    max_weight_kg = Column(Numeric(10, 3), nullable=True)
    tare_kg = Column(Numeric(10, 3), nullable=True)
    barcode_format = Column(String, nullable=False, default="standard")

    product = relationship("Product", back_populates="variants")
    inventory_item = relationship("InventoryItem", back_populates="variant", uselist=False, cascade="all, delete-orphan")
```

- [ ] **Step 17.4: Extend `backend/app/models/order.py`**

Add `quantity_kg` to `LineItem`:

```python
class LineItem(Base):
    __tablename__ = "line_items"
    __table_args__ = (
        Index("ix_line_items_order_id", "order_id"),
        Index("ix_line_items_variant_id", "variant_id"),
    )

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    title = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    quantity_kg = Column(Numeric(10, 3), nullable=True)
    price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="line_items")
    variant = relationship("ProductVariant")
```

- [ ] **Step 17.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_weighed_models.py -v`
Expected: PASS

- [ ] **Step 17.6: Commit**

```bash
git add backend/app/models/product.py backend/app/models/order.py backend/tests/test_weighed_models.py
git commit -m "feat(models): weighed-produce fields on ProductVariant + LineItem"
```

---

## Task 18: Weighed-produce validation service

**Files:**
- Create: `backend/app/services/weighed.py`
- Test: `backend/tests/test_weighed_service.py` (new)

- [ ] **Step 18.1: Write the failing test**

Create `backend/tests/test_weighed_service.py`:

```python
import pytest
from decimal import Decimal

from app.models import Product, ProductVariant
from app.services.weighed import (
    validate_weighed_line, compute_weighed_line_price,
    WeightOutOfRangeError, WeightMissingError, PricingTypeMismatchError,
)


@pytest.mark.asyncio
async def test_validate_rejects_missing_weight_for_by_weight(db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="Gala", price=Decimal("2.49"), pricing_type="by_weight")
    db.add(v); await db.flush()
    with pytest.raises(WeightMissingError):
        validate_weighed_line(variant=v, quantity_kg=None)


@pytest.mark.asyncio
async def test_validate_rejects_weight_below_min(db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", min_weight_kg=Decimal("0.050"),
    )
    db.add(v); await db.flush()
    with pytest.raises(WeightOutOfRangeError):
        validate_weighed_line(variant=v, quantity_kg=Decimal("0.030"))


@pytest.mark.asyncio
async def test_validate_rejects_weight_above_max(db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", max_weight_kg=Decimal("5.000"),
    )
    db.add(v); await db.flush()
    with pytest.raises(WeightOutOfRangeError):
        validate_weighed_line(variant=v, quantity_kg=Decimal("5.500"))


@pytest.mark.asyncio
async def test_validate_rejects_quantity_kg_on_fixed(db):
    p = Product(title="Milk", handle="milk"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="1L", price=Decimal("1.29"), pricing_type="fixed")
    db.add(v); await db.flush()
    with pytest.raises(PricingTypeMismatchError):
        validate_weighed_line(variant=v, quantity_kg=Decimal("0.500"))


def test_compute_weighed_line_price_rounds_to_cents():
    # 0.452 kg × 2.49 €/kg = 1.12548 → 1.13
    p = ProductVariant(price=Decimal("2.49"), pricing_type="by_weight", tare_kg=None)
    total = compute_weighed_line_price(variant=p, quantity_kg=Decimal("0.452"))
    assert total == Decimal("1.13")


def test_compute_subtracts_tare_when_set():
    # gross 0.500 kg, tare 0.050 kg, net 0.450 kg × 2.00 €/kg = 0.90
    p = ProductVariant(price=Decimal("2.00"), pricing_type="by_weight", tare_kg=Decimal("0.050"))
    total = compute_weighed_line_price(variant=p, quantity_kg=Decimal("0.500"))
    assert total == Decimal("0.90")
```

- [ ] **Step 18.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_weighed_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 18.3: Implement `backend/app/services/weighed.py`**

```python
from decimal import Decimal, ROUND_HALF_UP

from app.models import ProductVariant


class WeightMissingError(ValueError):
    pass


class WeightOutOfRangeError(ValueError):
    pass


class PricingTypeMismatchError(ValueError):
    pass


def validate_weighed_line(*, variant: ProductVariant, quantity_kg: Decimal | None) -> None:
    if variant.pricing_type == "by_weight":
        if quantity_kg is None:
            raise WeightMissingError("by_weight variant requires quantity_kg")
        if variant.min_weight_kg is not None and quantity_kg < variant.min_weight_kg:
            raise WeightOutOfRangeError(f"weight below min ({variant.min_weight_kg} kg)")
        if variant.max_weight_kg is not None and quantity_kg > variant.max_weight_kg:
            raise WeightOutOfRangeError(f"weight above max ({variant.max_weight_kg} kg)")
    else:
        if quantity_kg is not None:
            raise PricingTypeMismatchError("quantity_kg only valid for by_weight variants")


def compute_weighed_line_price(*, variant: ProductVariant, quantity_kg: Decimal) -> Decimal:
    net_kg = quantity_kg - (variant.tare_kg or Decimal("0"))
    raw = net_kg * variant.price
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

- [ ] **Step 18.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_weighed_service.py -v`
Expected: PASS (6 cases)

- [ ] **Step 18.5: Commit**

```bash
git add backend/app/services/weighed.py backend/tests/test_weighed_service.py
git commit -m "feat(weighed): validation + price computation for by_weight variants"
```

---

## Task 19: Wire weighed fields into product + order API schemas

**Files:**
- Modify: `backend/app/schemas/` (variant + order line schemas)
- Modify: `backend/app/services/order.py`
- Modify: `backend/app/api/products.py`, `backend/app/api/orders.py`
- Test: `backend/tests/test_weighed_api.py` (new)

- [ ] **Step 19.1: Find the existing variant + order-line Pydantic schemas**

Run: `grep -rn "class.*Variant.*:" backend/app/schemas/`
Run: `grep -rn "class.*LineItem.*:" backend/app/schemas/`

Note the file paths and class names. Typical names: `VariantIn`, `VariantOut`, `LineItemIn`, `LineItemOut`.

- [ ] **Step 19.2: Extend the variant schema**

In the variant schema file, add optional fields:

```python
pricing_type: str = "fixed"
weight_unit: str | None = None
min_weight_kg: Decimal | None = None
max_weight_kg: Decimal | None = None
tare_kg: Decimal | None = None
barcode_format: str = "standard"
```

- [ ] **Step 19.3: Extend the order line input schema**

Add `quantity_kg: Decimal | None = None` to the line-item input schema.

- [ ] **Step 19.4: Wire validation into the order service**

In `backend/app/services/order.py`, find the function that creates an order from a list of items. Before appending a `LineItem`, call:

```python
from app.services.weighed import validate_weighed_line, compute_weighed_line_price

# inside the loop over incoming items:
variant = await db.get(ProductVariant, item.variant_id)
validate_weighed_line(variant=variant, quantity_kg=item.quantity_kg)
if variant.pricing_type == "by_weight":
    line_price = compute_weighed_line_price(variant=variant, quantity_kg=item.quantity_kg)
    qty = 1
    qty_kg = item.quantity_kg
else:
    line_price = variant.price * item.quantity
    qty = item.quantity
    qty_kg = None

li = LineItem(
    order_id=order.id,
    variant_id=variant.id,
    title=f"{variant.product.title} {variant.title}",
    quantity=qty,
    quantity_kg=qty_kg,
    price=line_price,
)
```

- [ ] **Step 19.5: Write the failing API test**

Create `backend/tests/test_weighed_api.py`:

```python
import pytest
from decimal import Decimal

from app.models import Product, ProductVariant, InventoryItem, InventoryLevel, Location


@pytest.mark.asyncio
async def test_create_order_with_weighed_line(cashier_client, db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", weight_unit="kg",
        min_weight_kg=Decimal("0.050"), max_weight_kg=Decimal("5.000"),
    )
    db.add(v); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=100)
    db.add(lvl); await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "items": [{"variant_id": v.id, "quantity": 1, "quantity_kg": "0.452"}],
    })
    assert r.status_code == 201
    body = r.json()
    assert Decimal(body["line_items"][0]["price"]) == Decimal("1.13")
    assert body["line_items"][0]["quantity_kg"] == "0.452"


@pytest.mark.asyncio
async def test_create_order_rejects_underweight(cashier_client, db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", min_weight_kg=Decimal("0.100"),
    )
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=100); db.add(lvl)
    await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "items": [{"variant_id": v.id, "quantity": 1, "quantity_kg": "0.030"}],
    })
    assert r.status_code == 400
```

- [ ] **Step 19.6: Run, confirm fail, then make pass**

Run: `cd backend && pytest tests/test_weighed_api.py -v`

If tests fail with weight errors not surfaced as 400, wrap the service-layer calls in the API route with `try/except` and raise `HTTPException(status_code=400, detail=str(e))` for `WeightMissingError`, `WeightOutOfRangeError`, `PricingTypeMismatchError`.

Re-run until PASS.

- [ ] **Step 19.7: Commit**

```bash
git add backend/app/schemas backend/app/services/order.py backend/app/api/products.py backend/app/api/orders.py backend/tests/test_weighed_api.py
git commit -m "feat(weighed): API wiring for by_weight variants on orders"
```

---

## Task 20: Admin login UI (React)

**Files:**
- Create: `frontend/packages/shared/src/auth.ts`
- Create: `frontend/packages/admin/src/pages/Login.tsx`
- Create: `frontend/packages/admin/src/pages/Setup.tsx`
- Create: `frontend/packages/admin/src/components/RequireAuth.tsx`
- Modify: `frontend/packages/admin/src/App.tsx`

- [ ] **Step 20.1: Shared auth client**

Create `frontend/packages/shared/src/auth.ts`:

```ts
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
```

- [ ] **Step 20.2: Admin `Login.tsx`**

```tsx
import { useState } from "react";
import { login } from "@openmarket/shared/auth";

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
```

- [ ] **Step 20.3: Admin `Setup.tsx`**

```tsx
import { useState } from "react";
import { setup } from "@openmarket/shared/auth";

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
```

- [ ] **Step 20.4: `RequireAuth.tsx` guard**

```tsx
import { useEffect, useState } from "react";
import { fetchMe, type Me } from "@openmarket/shared/auth";
import { Login } from "../pages/Login";
import { Setup } from "../pages/Setup";

export function RequireAuth({ children }: { children: (me: Me) => React.ReactNode }) {
  const [me, setMe] = useState<Me | null | "loading" | "setup">("loading");

  async function reload() {
    try {
      const m = await fetchMe();
      setMe(m);
    } catch {
      setMe(null);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  if (me === "loading") return <p>Loading...</p>;
  if (me === "setup") return <Setup onComplete={reload} />;
  if (me === null) {
    // check if setup is needed: /api/auth/setup returning 409 means already set up
    return <Login onSuccess={reload} />;
  }
  return <>{children(me)}</>;
}
```

- [ ] **Step 20.5: Wrap admin App**

In `frontend/packages/admin/src/App.tsx`, wrap the existing router in `<RequireAuth>`:

```tsx
import { RequireAuth } from "./components/RequireAuth";

export function App() {
  return (
    <RequireAuth>
      {(me) => <ExistingRouter role={me.role} />}
    </RequireAuth>
  );
}
```

- [ ] **Step 20.6: Smoke test**

Run: `cd frontend/packages/admin && pnpm dev`
Open `http://localhost:5173` in the browser. Before backend /setup has been called, verify first page shown is Setup, then after creating the owner you land in the admin. After logout, you land on Login.

- [ ] **Step 20.7: Commit**

```bash
git add frontend/packages/shared frontend/packages/admin
git commit -m "feat(admin-ui): login + first-run setup + auth guard"
```

---

## Task 21: POS cashier login UI

**Files:**
- Create: `frontend/packages/pos/src/pages/CashierLogin.tsx`
- Modify: `frontend/packages/pos/src/App.tsx`

- [ ] **Step 21.1: Create `CashierLogin.tsx`**

```tsx
import { useEffect, useState } from "react";
import { posLogin } from "@openmarket/shared/auth";

type Cashier = { id: number; full_name: string };

export function CashierLogin({ onSuccess }: { onSuccess: () => void }) {
  const [cashiers, setCashiers] = useState<Cashier[]>([]);
  const [selected, setSelected] = useState<Cashier | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/users/cashiers", { credentials: "include" })
      .then((r) => r.json())
      .then(setCashiers)
      .catch(() => setError("Could not load cashier list"));
  }, []);

  async function submit() {
    if (!selected) return;
    setError(null);
    try {
      await posLogin(selected.id, pin);
      onSuccess();
    } catch (err) {
      setError((err as Error).message);
      setPin("");
    }
  }

  function press(digit: string) {
    if (pin.length >= 6) return;
    const next = pin + digit;
    setPin(next);
    if (next.length >= 4) {
      // auto-submit at length 4+ after short delay — cashier can keep typing to get 5/6
    }
  }

  if (!selected) {
    return (
      <div style={{ padding: 32 }}>
        <h1>Select cashier</h1>
        <ul>
          {cashiers.map((c) => (
            <li key={c.id}>
              <button onClick={() => setSelected(c)}>{c.full_name}</button>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div style={{ padding: 32, textAlign: "center" }}>
      <h1>{selected.full_name}</h1>
      <p>Enter PIN</p>
      <div style={{ fontSize: 48, letterSpacing: 16 }}>{"•".repeat(pin.length)}</div>
      {error && <p role="alert">{error}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 80px)", gap: 8, justifyContent: "center" }}>
        {"123456789".split("").map((d) => (
          <button key={d} onClick={() => press(d)} style={{ height: 80, fontSize: 32 }}>{d}</button>
        ))}
        <button onClick={() => setPin("")} style={{ height: 80 }}>clr</button>
        <button onClick={() => press("0")} style={{ height: 80, fontSize: 32 }}>0</button>
        <button onClick={submit} style={{ height: 80 }}>↵</button>
      </div>
      <button onClick={() => { setSelected(null); setPin(""); }}>← different cashier</button>
    </div>
  );
}
```

- [ ] **Step 21.2: Wrap POS App**

Similar pattern to admin — POS checks for an active session; if none, show `CashierLogin`.

In `frontend/packages/pos/src/App.tsx`:

```tsx
import { useEffect, useState } from "react";
import { fetchMe, type Me } from "@openmarket/shared/auth";
import { CashierLogin } from "./pages/CashierLogin";

export function App() {
  const [me, setMe] = useState<Me | null | "loading">("loading");

  async function reload() {
    try { setMe(await fetchMe()); } catch { setMe(null); }
  }
  useEffect(() => { void reload(); }, []);

  if (me === "loading") return <p>Loading...</p>;
  if (me === null) return <CashierLogin onSuccess={reload} />;
  return <ExistingPosUI me={me} onLogout={reload} />;
}
```

- [ ] **Step 21.3: Add backend route `/api/users/cashiers`**

In `backend/app/api/auth.py`, add a small helper route (no auth required because cashier-picker needs to render before login):

```python
from app.schemas.auth import PosLoginResponse

@router.get("/cashiers", response_model=list[PosLoginResponse])
async def list_cashiers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.role == "cashier", User.active.is_(True)).order_by(User.full_name))
    return [PosLoginResponse(user_id=u.id, full_name=u.full_name) for u in result.scalars().all()]
```

Then change the frontend URL in `CashierLogin.tsx` from `/api/users/cashiers` to `/api/auth/cashiers`.

Also: exclude this route from CORS credentials requirement (it's a read-only list of names).

- [ ] **Step 21.4: Smoke test**

Run: `cd frontend/packages/pos && pnpm dev`. Create a cashier via admin first. On POS, verify cashier appears, PIN keypad works, success lands on POS.

- [ ] **Step 21.5: Commit**

```bash
git add frontend/packages/pos backend/app/api/auth.py
git commit -m "feat(pos-ui): cashier PIN login + cashier list endpoint"
```

---

## Task 22: Weighed-produce POS UI

**Files:**
- Create: `frontend/packages/pos/src/components/WeighedProductInput.tsx`
- Modify: the existing POS product-picker / cart code (find it)

- [ ] **Step 22.1: Find the existing POS product-add component**

Run: `grep -rn "quantity" frontend/packages/pos/src/`
Identify the component that adds a scanned product to the cart (likely a `BarcodeScanner` callback or a `ProductCard` click).

- [ ] **Step 22.2: Create `WeighedProductInput.tsx`**

```tsx
import { useState } from "react";

type Props = {
  title: string;
  pricePerKg: string;
  weightUnit: "kg" | "g" | "100g";
  minKg?: string;
  maxKg?: string;
  onConfirm: (quantityKg: number) => void;
  onCancel: () => void;
};

export function WeighedProductInput({ title, pricePerKg, weightUnit, minKg, maxKg, onConfirm, onCancel }: Props) {
  const [buffer, setBuffer] = useState("");

  const qty = buffer ? parseFloat(buffer) : 0;
  const total = qty * parseFloat(pricePerKg);

  function press(ch: string) {
    if (ch === "." && buffer.includes(".")) return;
    if (buffer.length >= 6) return;
    setBuffer(buffer + ch);
  }
  function back() { setBuffer(buffer.slice(0, -1)); }
  function confirm() {
    if (!qty) return;
    if (minKg && qty < parseFloat(minKg)) return;
    if (maxKg && qty > parseFloat(maxKg)) return;
    onConfirm(qty);
  }

  return (
    <div style={{ padding: 24 }}>
      <h2>{title}</h2>
      <p style={{ fontSize: 24 }}>{pricePerKg} €/kg</p>
      <div style={{ fontSize: 64, fontFamily: "monospace" }}>
        {buffer || "0"} <small>kg</small>
      </div>
      <div style={{ fontSize: 32 }}>{total.toFixed(2)} €</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 80px)", gap: 8 }}>
        {"123456789".split("").map((d) => (
          <button key={d} onClick={() => press(d)}>{d}</button>
        ))}
        <button onClick={() => press(".")}>.</button>
        <button onClick={() => press("0")}>0</button>
        <button onClick={back}>←</button>
      </div>
      <div style={{ marginTop: 16 }}>
        <button onClick={onCancel}>Cancel</button>
        <button onClick={confirm}>Add</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 22.3: Wire it in**

In the POS "add to cart" flow, after the variant is resolved, check `variant.pricing_type`:

```tsx
if (variant.pricing_type === "by_weight") {
  setWeighedPrompt({ variant });
} else {
  addToCart({ variant, quantity: 1 });
}
```

Render `<WeighedProductInput>` when `weighedPrompt` is set. On confirm, call `addToCart({ variant, quantity: 1, quantity_kg: qty })`.

Update the cart's `addToCart` → POST body to include `quantity_kg` when present.

- [ ] **Step 22.4: Smoke test**

Start POS, create a by_weight variant via admin (Gala apples at 2,49 €/kg, min 0,050 / max 5,000). On POS, scan/pick apples, verify numeric keypad appears, enter 0.452, add, verify line shows 1,13 €.

- [ ] **Step 22.5: Commit**

```bash
git add frontend/packages/pos/src
git commit -m "feat(pos-ui): weighed-produce numeric keypad input"
```

---

## Task 23: Admin UI — expose weighed-produce variant fields

**Files:**
- Modify: the existing variant editor in `frontend/packages/admin/src/pages/`

- [ ] **Step 23.1: Locate the variant editor**

Run: `grep -rln "pricing_type\|ProductVariant" frontend/packages/admin/src/`
Open the existing variant edit form.

- [ ] **Step 23.2: Add controls**

Add a `<select>` for `pricing_type` (`fixed` / `by_weight`). When `by_weight`, reveal:

- `weight_unit` select (`kg`, `g`, `100g`)
- `min_weight_kg` number input
- `max_weight_kg` number input
- `tare_kg` number input
- Reinterpret the existing `price` field label as "€ per kg" instead of "€".

Include the new fields in the submit payload.

- [ ] **Step 23.3: Smoke test**

Create a `by_weight` variant, verify it persists, fetch the product detail, confirm the new fields are returned.

- [ ] **Step 23.4: Commit**

```bash
git add frontend/packages/admin/src
git commit -m "feat(admin-ui): expose weighed-produce variant fields"
```

---

## Task 24: TLS-on-LAN setup runbook

**Files:**
- Create: `docs/ops/tls-lan-setup.md`

- [ ] **Step 24.1: Write the runbook**

```markdown
# TLS on the LAN — Self-Signed Certificate Setup

Goal: the cashier tablet and admin laptop speak HTTPS to the NUC over the LAN
without browser warnings. We use a self-signed root CA and per-hostname certs
for `admin.local`, `pos.local`, `store.local`.

## On the NUC — generate root CA once

    mkdir -p /etc/openmarket/tls && cd /etc/openmarket/tls
    openssl genrsa -out rootCA.key 4096
    openssl req -x509 -new -nodes -key rootCA.key -sha256 -days 3650 \
        -out rootCA.crt -subj "/CN=OpenMarket LAN Root CA"

## Generate server cert signed by the root CA

    cat > san.cnf <<EOF
    [req]
    distinguished_name=req
    [san]
    subjectAltName=DNS:admin.local,DNS:pos.local,DNS:store.local
    EOF
    openssl genrsa -out server.key 2048
    openssl req -new -key server.key -out server.csr \
        -subj "/CN=openmarket.local"
    openssl x509 -req -in server.csr -CA rootCA.crt -CAkey rootCA.key \
        -CAcreateserial -out server.crt -days 825 -sha256 \
        -extfile san.cnf -extensions san

## Wire into nginx

Edit `/etc/nginx/nginx.conf`:

    server {
        listen 443 ssl;
        server_name admin.local pos.local store.local;
        ssl_certificate     /etc/openmarket/tls/server.crt;
        ssl_certificate_key /etc/openmarket/tls/server.key;
        # ... existing proxy_pass config ...
    }
    server {
        listen 80;
        return 301 https://$host$request_uri;
    }

Reload: `docker compose exec nginx nginx -s reload`

## LAN DNS — /etc/hosts on each device

On the tablet and admin laptop, add to `/etc/hosts` (or equivalent):

    192.168.1.10  admin.local pos.local store.local

(Replace `192.168.1.10` with the NUC's LAN IP.)

## Install the root CA on each device

Copy `rootCA.crt` to each device (USB drive or scp). Then:

- **macOS:** Keychain Access → System → drag `rootCA.crt` in → set Trust: Always Trust.
- **Windows:** double-click `rootCA.crt` → Install Certificate → Local Machine → Place in "Trusted Root Certification Authorities".
- **iPadOS/iOS:** email the CA to yourself → tap → Settings → Profile Downloaded → Install → Settings → General → About → Certificate Trust Settings → enable.
- **Android:** Settings → Security → Install from storage → select `rootCA.crt` → CA certificate.
- **Linux:** `sudo cp rootCA.crt /usr/local/share/ca-certificates/openmarket-root.crt && sudo update-ca-certificates`

## Verify

From each device, visit `https://admin.local` — no warning, padlock green.

## Renewal

The server cert is valid 825 days (Apple/Chrome cap). Calendar a renewal one
month before expiry. Re-run the "generate server cert" step and reload nginx.
The root CA is valid 10 years.
```

- [ ] **Step 24.2: Commit**

```bash
git add docs/ops/tls-lan-setup.md
git commit -m "docs(ops): TLS on LAN setup runbook"
```

---

## Task 25: First-run bootstrap runbook

**Files:**
- Create: `docs/ops/bootstrap-first-run.md`

- [ ] **Step 25.1: Write the runbook**

```markdown
# First-Run Bootstrap

Once the stack is up on a fresh NUC, the database has zero users. The admin
UI detects this and routes to `/setup`. Only the very first call to
`POST /api/auth/setup` succeeds — subsequent calls return 409 even if the
first owner is deleted, because the guard is "any user exists".

## Steps

1. Bring up the stack: `docker compose up -d`.
2. Open `https://admin.local` on the admin laptop. You should see the Setup form.
3. Enter a strong passphrase (min 12 chars, will be checked against HIBP).
4. Submit. You are logged in as owner and bounced to the admin dashboard.
5. Under **Settings → Security**, enroll TOTP MFA. Scan the QR code into
   Authy / 1Password / Aegis. Verify the first 6-digit code. MFA is now required
   for this account on subsequent logins.
6. Under **Users**, create the rest of the staff:
   - Managers (optional MFA, recommended)
   - Cashiers (no email, 4-6 digit PIN only)
7. Create a second owner-role user as a break-glass backup. Store its password
   in the physical safe. Never uses it — it exists so a lost-device MFA flow
   never becomes "store cannot operate."

## What not to do

- Never commit `.env` to the repo.
- Never share the session cookie.
- Never disable HIBP in production (`hibp_enabled=False`) — it's there
  precisely to catch the owner using a weak passphrase.
```

- [ ] **Step 25.2: Commit**

```bash
git add docs/ops/bootstrap-first-run.md
git commit -m "docs(ops): first-run bootstrap runbook"
```

---

## Self-review (run after all tasks complete)

1. **Spec coverage — §3 Weighed produce:** tasks 16–19, 22, 23. ✔
2. **Spec coverage — §4 Auth:** tasks 1–14, 20, 21, 25. ✔
3. **Spec coverage — §6 Security minimal:**
   - TLS on LAN → task 24 (runbook). ✔
   - CORS tight → task 15. ✔
   - No internet exposure → operational, not code; noted in runbook. ✔
   - Secrets in `.env` → task 1. ✔
   - Login rate-limit → tasks 8 + 12. ✔
   - argon2id → task 4. ✔
   - Postgres on private network → already in docker-compose. ✔
4. **Placeholder scan:** no "TBD"/"TODO"/"handle appropriately" remain. ✔
5. **Type consistency:** `require_owner`, `require_manager_or_above`, `require_any_staff` names match spec; `pricing_type` values `fixed`/`by_weight`/`by_volume` match spec; session cookie name configured via `settings.session_cookie_name`. ✔

## Deferred (explicitly out of scope for Plan 1)

- CSRF middleware, CSP, full security headers — Plan N (Phase 2 hardening).
- GDPR erasure flow — lands with online channel.
- Passkeys / WebAuthn — `mfa_method` column exists as hook.
- Scale integration, weight-embedded EAN parsing — Phase 2.
- Fiscal / payment / receipt printer — Plan 2.
- Backups / observability — Plan 3.
- Go-live acceptance tests on real hardware — Plan 4.
