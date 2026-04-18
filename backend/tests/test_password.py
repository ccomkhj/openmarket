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
