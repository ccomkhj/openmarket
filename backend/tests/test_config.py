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
