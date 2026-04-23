"""Kassenbuch — daily cash shift entries (open/close/paid-in/paid-out)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KassenbuchEntry


@dataclass
class CloseSummary:
    entry: KassenbuchEntry
    expected: Decimal
    counted: Decimal
    difference: Decimal


def _denomination_total(denominations: Mapping[str, int]) -> Decimal:
    total = Decimal("0")
    for value, count in denominations.items():
        total += Decimal(value) * Decimal(int(count))
    return total.quantize(Decimal("0.01"))


class KassenbuchService:
    def __init__(self, *, db: AsyncSession):
        self.db = db

    async def open_shift(
        self, *, cashier_user_id: int, denominations: Mapping[str, int],
    ) -> KassenbuchEntry:
        amount = _denomination_total(denominations)
        e = KassenbuchEntry(
            entry_type="open", amount=amount,
            denominations={k: int(v) for k, v in denominations.items()},
            cashier_user_id=cashier_user_id,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.db.add(e)
        await self.db.commit(); await self.db.refresh(e)
        return e

    async def paid_in(self, *, cashier_user_id: int, amount: Decimal, reason: str) -> KassenbuchEntry:
        if not reason:
            raise ValueError("paid_in requires a reason")
        e = KassenbuchEntry(
            entry_type="paid_in", amount=amount.quantize(Decimal("0.01")),
            cashier_user_id=cashier_user_id, reason=reason,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.db.add(e)
        await self.db.commit(); await self.db.refresh(e)
        return e

    async def paid_out(self, *, cashier_user_id: int, amount: Decimal, reason: str) -> KassenbuchEntry:
        if not reason:
            raise ValueError("paid_out requires a reason")
        e = KassenbuchEntry(
            entry_type="paid_out", amount=-amount.quantize(Decimal("0.01")),
            cashier_user_id=cashier_user_id, reason=reason,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.db.add(e)
        await self.db.commit(); await self.db.refresh(e)
        return e

    async def close_shift(
        self, *, cashier_user_id: int, denominations: Mapping[str, int],
    ) -> CloseSummary:
        entries = (await self.db.execute(select(KassenbuchEntry))).scalars().all()
        expected = sum((e.amount for e in entries), Decimal("0")).quantize(Decimal("0.01"))
        counted = _denomination_total(denominations)
        diff = (counted - expected).quantize(Decimal("0.01"))

        e = KassenbuchEntry(
            entry_type="close", amount=counted,
            denominations={k: int(v) for k, v in denominations.items()},
            reason=None if diff == 0 else f"Kassendifferenz {diff}",
            cashier_user_id=cashier_user_id,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.db.add(e)
        await self.db.commit(); await self.db.refresh(e)
        return CloseSummary(entry=e, expected=expected, counted=counted, difference=diff)
