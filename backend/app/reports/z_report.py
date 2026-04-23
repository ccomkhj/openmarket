"""Z-Report — daily shift summary aggregator."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KassenbuchEntry, PosTransaction


@dataclass
class ZReport:
    date_from: datetime
    date_to: datetime
    opening_cash: Decimal = Decimal("0")
    closing_counted: Decimal = Decimal("0")
    transaction_count: int = 0
    sales_by_vat: dict[str, Decimal] = field(default_factory=dict)
    sales_by_payment: dict[str, Decimal] = field(default_factory=dict)
    paid_in_total: Decimal = Decimal("0")
    paid_out_total: Decimal = Decimal("0")
    signature_counter_first: int | None = None
    signature_counter_last: int | None = None


class ZReportBuilder:
    def __init__(self, *, db: AsyncSession):
        self.db = db

    async def build(self, *, date_from: datetime, date_to: datetime) -> ZReport:
        rpt = ZReport(date_from=date_from, date_to=date_to)

        kb = (await self.db.execute(
            select(KassenbuchEntry).where(
                and_(KassenbuchEntry.timestamp >= date_from,
                     KassenbuchEntry.timestamp <= date_to)
            ).order_by(KassenbuchEntry.timestamp)
        )).scalars().all()
        for e in kb:
            if e.entry_type == "open":
                rpt.opening_cash = Decimal(e.amount)
            elif e.entry_type == "close":
                rpt.closing_counted = Decimal(e.amount)
            elif e.entry_type == "paid_in":
                rpt.paid_in_total += Decimal(e.amount)
            elif e.entry_type == "paid_out":
                rpt.paid_out_total += -Decimal(e.amount)

        txs = (await self.db.execute(
            select(PosTransaction).where(
                and_(PosTransaction.started_at >= date_from,
                     PosTransaction.started_at <= date_to)
            ).order_by(PosTransaction.started_at)
        )).scalars().all()
        rpt.transaction_count = len(txs)
        counters = [t.tse_signature_counter for t in txs if t.tse_signature_counter is not None]
        if counters:
            rpt.signature_counter_first = min(counters)
            rpt.signature_counter_last = max(counters)
        for t in txs:
            for slot, row in (t.vat_breakdown or {}).items():
                rpt.sales_by_vat[slot] = (
                    rpt.sales_by_vat.get(slot, Decimal("0")) + Decimal(row.get("gross", "0"))
                )
            for method, amount in (t.payment_breakdown or {}).items():
                rpt.sales_by_payment[method] = (
                    rpt.sales_by_payment.get(method, Decimal("0")) + Decimal(amount)
                )
        return rpt
