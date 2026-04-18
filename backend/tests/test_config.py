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


def test_settings_rejects_change_me_substring():
    with pytest.raises(ValidationError):
        Settings(session_secret_key="CHANGE_ME_" + "x" * 48)


def test_settings_rejects_changeme_variants():
    for v in ("Change Me 1234567890 1234567890 abcd", "ChangeMeChangeMeChangeMeChangeMe"):
        with pytest.raises(ValidationError):
            Settings(session_secret_key=v)


def test_settings_parses_lan_ip_cidrs():
    s = Settings(session_secret_key="x" * 48, lan_ip_cidrs="10.0.0.0/8, 192.168.0.0/16")
    assert s.lan_ip_cidr_list == ["10.0.0.0/8", "192.168.0.0/16"]


def test_settings_parses_allowed_cors_origins():
    s = Settings(session_secret_key="x" * 48, allowed_cors_origins="https://a.local,https://b.local, ")
    assert s.allowed_cors_origin_list == ["https://a.local", "https://b.local"]
