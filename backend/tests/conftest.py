import os

# Must run before any `from app.*` import so Settings() sees a valid secret.
os.environ.setdefault("SESSION_SECRET_KEY", "x" * 48)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.api.deps import get_db  # noqa: E402
from app.models import *  # noqa: F401, F403, E402

TEST_DB_URL = "postgresql+asyncpg://openmarket:openmarket@localhost:5433/openmarket_test"


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
