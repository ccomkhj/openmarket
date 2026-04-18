import pyotp
import pytest

from app.services.mfa import new_totp_secret, totp_uri, verify_totp


def test_new_secret_is_base32():
    s = new_totp_secret()
    assert len(s) >= 16
    pyotp.TOTP(s).now()  # raises if not base32


def test_totp_uri_has_issuer_and_user():
    uri = totp_uri(secret="JBSWY3DPEHPK3PXP", user_email="owner@example.com")
    assert "OpenMarket" in uri
    # pyotp URL-encodes the '@' per RFC 3986, so check for the encoded form.
    assert "owner%40example.com" in uri


def test_verify_totp_accepts_current_code():
    s = new_totp_secret()
    code = pyotp.TOTP(s).now()
    assert verify_totp(secret=s, code=code) is True


def test_verify_totp_rejects_wrong_code():
    s = new_totp_secret()
    assert verify_totp(secret=s, code="000000") is False
