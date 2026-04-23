"""Low-level fiskaly REST client with OAuth2 token caching and retry."""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential,
    RetryError,
)

from app.fiscal.errors import (
    FiscalAuthError, FiscalBadRequestError, FiscalNetworkError,
    FiscalNotConfiguredError, FiscalServerError,
)


class FiscalClient:
    def __init__(
        self, *,
        api_key: str, api_secret: str, tss_id: str, base_url: str,
        http: Optional[httpx.AsyncClient] = None,
        timeout_s: float = 10.0,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.tss_id = tss_id
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=timeout_s)
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _ensure_configured(self) -> None:
        if not (self.api_key and self.api_secret and self.tss_id):
            raise FiscalNotConfiguredError("fiskaly env vars missing")

    async def _get_token(self) -> str:
        self._ensure_configured()
        now = time.time()
        if self._token and now < self._token_expires_at - 30:
            return self._token
        r = await self._http.post(
            f"{self.base_url}/api/v2/auth",
            json={"api_key": self.api_key, "api_secret": self.api_secret},
        )
        if r.status_code >= 400:
            raise FiscalAuthError(f"auth failed: {r.status_code} {r.text}")
        data = r.json()
        self._token = data["access_token"]
        self._token_expires_at = now + int(data.get("access_token_expires_in", 300))
        return self._token

    async def _request(self, method: str, path: str, **kw) -> dict[str, Any]:
        @retry(
            retry=retry_if_exception_type((httpx.TransportError, _Retryable5xx)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=20),
            reraise=True,
        )
        async def _do() -> dict[str, Any]:
            token = await self._get_token()
            headers = {**kw.pop("headers", {}), "Authorization": f"Bearer {token}"}
            r = await self._http.request(
                method, f"{self.base_url}{path}", headers=headers, **kw,
            )
            if r.status_code == 401:
                self._token = None
                raise _Retryable5xx(f"401 re-auth {r.text}")
            if 500 <= r.status_code < 600:
                raise _Retryable5xx(f"{r.status_code} {r.text}")
            if 400 <= r.status_code < 500:
                raise FiscalBadRequestError(f"{r.status_code} {r.text}")
            return r.json() if r.content else {}

        try:
            return await _do()
        except RetryError as e:
            inner = e.last_attempt.exception() if e.last_attempt else None
            if isinstance(inner, _Retryable5xx):
                raise FiscalServerError(str(inner)) from inner
            if isinstance(inner, httpx.TransportError):
                raise FiscalNetworkError(str(inner)) from inner
            raise

    async def put(self, path: str, *, json: dict) -> dict[str, Any]:
        return await self._request("PUT", path, json=json)

    async def post(self, path: str, *, json: dict) -> dict[str, Any]:
        return await self._request("POST", path, json=json)


class _Retryable5xx(Exception):
    """Sentinel to drive tenacity retry on 5xx/401."""
    pass
