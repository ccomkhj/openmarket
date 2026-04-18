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
