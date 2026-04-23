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


def test_settings_parses_trusted_proxy_cidrs_default():
    s = Settings(session_secret_key="x" * 48)
    assert s.trusted_proxy_cidr_list == ["127.0.0.1/32"]


def test_settings_parses_trusted_proxy_cidrs_custom():
    s = Settings(
        session_secret_key="x" * 48,
        trusted_proxy_cidrs="127.0.0.1/32, 172.20.0.0/16",
    )
    assert s.trusted_proxy_cidr_list == ["127.0.0.1/32", "172.20.0.0/16"]


def test_settings_parses_fiskaly_config():
    s = Settings(
        session_secret_key="x" * 48,
        fiskaly_api_key="key-123",
        fiskaly_api_secret="secret-456",
        fiskaly_tss_id="tss-abc",
    )
    assert s.fiskaly_api_key == "key-123"
    assert s.fiskaly_api_secret == "secret-456"
    assert s.fiskaly_tss_id == "tss-abc"
    assert s.fiskaly_base_url == "https://kassensichv-middleware.fiskaly.com"


def test_settings_fiskaly_base_url_overridable():
    s = Settings(
        session_secret_key="x" * 48,
        fiskaly_api_key="k", fiskaly_api_secret="s", fiskaly_tss_id="t",
        fiskaly_base_url="https://sandbox.example.com",
    )
    assert s.fiskaly_base_url == "https://sandbox.example.com"


def test_settings_parses_printer_config_defaults():
    s = Settings(session_secret_key="x" * 48)
    assert s.printer_vendor_id == 0x04b8  # Epson default
    assert s.printer_product_id == 0x0e28  # TM-m30III default
    assert s.printer_profile == "TM-m30III"


def test_settings_parses_printer_config_overrides():
    s = Settings(
        session_secret_key="x" * 48,
        printer_vendor_id=0x0519, printer_product_id=0x0003,
        printer_profile="TSP143",
    )
    assert s.printer_vendor_id == 0x0519
    assert s.printer_product_id == 0x0003
    assert s.printer_profile == "TSP143"


def test_settings_parses_terminal_config():
    s = Settings(
        session_secret_key="x" * 48,
        terminal_host="192.168.1.50", terminal_port=22000,
        terminal_password="000000",
    )
    assert s.terminal_host == "192.168.1.50"
    assert s.terminal_port == 22000
    assert s.terminal_password == "000000"


def test_settings_terminal_defaults_empty():
    s = Settings(session_secret_key="x" * 48)
    assert s.terminal_host == ""
    assert s.terminal_port == 22000
