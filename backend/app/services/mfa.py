import pyotp


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(*, secret: str, user_email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=user_email, issuer_name="OpenMarket")


def verify_totp(*, secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
