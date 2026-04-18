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
