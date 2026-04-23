class PaymentError(Exception):
    pass


class TerminalUnavailableError(PaymentError):
    pass


class CardDeclinedError(PaymentError):
    """Cardholder action: re-tap or pay another way."""


class TerminalTimeoutError(PaymentError):
    pass


class TerminalProtocolError(PaymentError):
    """Unexpected APDU; likely terminal misconfiguration."""
