import os

# Must run before any `from app.*` import so Settings() sees a valid secret.
os.environ.setdefault("SESSION_SECRET_KEY", "x" * 48)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.api.deps import get_db  # noqa: E402
from app.models import *  # noqa: F401, F403, E402
from app.models import User  # noqa: E402
from app.services.password import hash_password, hash_pin  # noqa: E402
from app.services.session import create_session  # noqa: E402

TEST_DB_URL = "postgresql+asyncpg://openmarket:openmarket@localhost:5433/openmarket_test"

_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION reject_audit_modification() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit rows are append-only';
END;
$$ LANGUAGE plpgsql
"""

_TRIGGER_UPDATE_DROP_SQL = "DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events"

_TRIGGER_UPDATE_SQL = """
CREATE TRIGGER audit_events_no_update
    BEFORE UPDATE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_audit_modification()
"""

_TRIGGER_DELETE_DROP_SQL = "DROP TRIGGER IF EXISTS audit_events_no_delete ON audit_events"

_TRIGGER_DELETE_SQL = """
CREATE TRIGGER audit_events_no_delete
    BEFORE DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_audit_modification()
"""

_FISCAL_REJECT_FN_SQL = """
CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$
BEGIN
    IF current_setting('fiscal.signing', true) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Fiscal rows are immutable (TG_OP=%, table=%)', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""

_FISCAL_TABLES = ("pos_transactions", "pos_transaction_lines", "tse_signing_log")


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
            await conn.execute(sa.text(_FISCAL_REJECT_FN_SQL))
            for tbl in _FISCAL_TABLES:
                await conn.execute(sa.text(
                    f"CREATE TRIGGER {tbl}_reject_update BEFORE UPDATE ON {tbl} "
                    f"FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification()"
                ))
                await conn.execute(sa.text(
                    f"CREATE TRIGGER {tbl}_reject_delete BEFORE DELETE ON {tbl} "
                    f"FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification()"
                ))
            # receipt_number_seq is normally created by Alembic; create here for tests
            await conn.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS receipt_number_seq START 1"))
        yield engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.execute(sa.text("DROP SEQUENCE IF EXISTS receipt_number_seq"))
            await conn.execute(sa.text("DROP FUNCTION IF EXISTS fiscal_reject_modification()"))
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db(setup_db):
    engine = setup_db
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        yield c
    app.dependency_overrides.clear()


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
