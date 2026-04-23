"""Payment-terminal abstraction. Production uses ZvtTerminal; tests use Mock."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from app.payment.errors import CardDeclinedError, TerminalUnavailableError


@dataclass
class AuthorizeResult:
    approved: bool
    amount: Decimal
    auth_code: str
    terminal_id: str
    trace_number: str
    receipt_number: str
    response_code: str
    raw: dict = field(default_factory=dict)


class PaymentTerminalBackend(Protocol):
    async def diagnose(self) -> bool: ...
    async def authorize(self, *, amount: Decimal) -> AuthorizeResult: ...
    async def reverse(self, *, trace_number: str) -> AuthorizeResult: ...
    async def end_of_day(self) -> dict: ...


class MockTerminal:
    """In-memory deterministic terminal for unit tests."""

    def __init__(self, *, online: bool = True, approve: bool = True):
        self.online = online
        self.approve = approve
        self._next_trace = 1
        self.calls: list[tuple[str, dict]] = []

    async def diagnose(self) -> bool:
        self.calls.append(("diagnose", {}))
        return self.online

    async def authorize(self, *, amount: Decimal) -> AuthorizeResult:
        self.calls.append(("authorize", {"amount": amount}))
        if not self.online:
            raise TerminalUnavailableError("mock offline")
        if not self.approve:
            raise CardDeclinedError("mock decline")
        trace = f"{self._next_trace:06d}"
        self._next_trace += 1
        return AuthorizeResult(
            approved=True, amount=amount,
            auth_code="123456", terminal_id="TID-MOCK", trace_number=trace,
            receipt_number=trace, response_code="00", raw={"mock": True},
        )

    async def reverse(self, *, trace_number: str) -> AuthorizeResult:
        self.calls.append(("reverse", {"trace_number": trace_number}))
        return AuthorizeResult(
            approved=True, amount=Decimal("0"), auth_code="000000",
            terminal_id="TID-MOCK", trace_number=trace_number,
            receipt_number=trace_number, response_code="00", raw={"reversed": True},
        )

    async def end_of_day(self) -> dict:
        self.calls.append(("end_of_day", {}))
        return {"completed": True, "transactions": self._next_trace - 1}
