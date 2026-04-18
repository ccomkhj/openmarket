from unittest.mock import AsyncMock, patch

import pytest

from app.services.password import (
    hash_password, verify_password, hash_pin, verify_pin, PasswordTooShortError,
    PinMalformedError, check_password_not_breached, PasswordBreachedError,
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


@pytest.mark.asyncio
async def test_hibp_accepts_unknown_password():
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = "0000000000000000000000000000000000A:1\nFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFB:2\n"
    with patch("app.services.password._hibp_get", return_value=mock_resp):
        await check_password_not_breached("never-before-seen-password-xyz")


@pytest.mark.asyncio
async def test_hibp_rejects_known_password():
    # SHA1("password1234") upper = E6B6AFBD6D76BB5D2041542D7D2E3FAC5BB05593
    # prefix E6B6A, suffix FBD6D76BB5D2041542D7D2E3FAC5BB05593
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.text = "FBD6D76BB5D2041542D7D2E3FAC5BB05593:3861493\n"
    with patch("app.services.password._hibp_get", return_value=mock_resp):
        with pytest.raises(PasswordBreachedError):
            await check_password_not_breached("password1234")


@pytest.mark.asyncio
async def test_hibp_tolerates_offline():
    with patch("app.services.password._hibp_get", side_effect=OSError("offline")):
        # offline fallback: does NOT raise
        await check_password_not_breached("any-password-value")
