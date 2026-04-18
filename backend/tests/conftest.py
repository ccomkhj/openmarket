import os

# Must run before any `from app.*` import so Settings() sees a valid secret.
os.environ.setdefault("SESSION_SECRET_KEY", "x" * 48)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.api.deps import get_db  # noqa: E402
from app.models import *  # noqa: F401, F403, E402

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


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(TEST_DB_URL)
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
