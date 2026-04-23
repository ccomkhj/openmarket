"""Exception hierarchy for fiskaly/TSE interactions."""


class FiscalError(Exception):
    """Base for all fiscal subsystem errors."""
    error_code: str = "FISCAL_UNKNOWN"


class FiscalAuthError(FiscalError):
    """OAuth2 token acquisition failed — credentials likely misconfigured."""
    error_code = "FISCAL_AUTH"


class FiscalNetworkError(FiscalError):
    """fiskaly unreachable or timed out after retries."""
    error_code = "FISCAL_NETWORK"


class FiscalServerError(FiscalError):
    """fiskaly returned 5xx after retries."""
    error_code = "FISCAL_SERVER"


class FiscalBadRequestError(FiscalError):
    """fiskaly returned 4xx — programmer error or bad config."""
    error_code = "FISCAL_BAD_REQUEST"


class FiscalNotConfiguredError(FiscalError):
    """FISKALY_* env vars are missing; no network call will be attempted."""
    error_code = "FISCAL_NOT_CONFIGURED"
