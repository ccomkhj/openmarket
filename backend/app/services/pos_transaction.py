"""Bind an Order + payment_breakdown into a TSE-signed PosTransaction."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.fiscal.errors import FiscalError
from app.fiscal.process_data import build_process_data
from app.fiscal.service import FiscalService
from app.models import (
    LineItem, Order, PosTransaction, PosTransactionLine, TaxRate,
)


class PosTransactionService:
    def __init__(self, *, db: AsyncSession, fiscal: FiscalService):
        self.db = db
        self.fiscal = fiscal

    async def finalize_sale(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
        payment_breakdown: Mapping[str, Decimal],
        voids_transaction_id: uuid.UUID | None = None,
    ) -> PosTransaction:
        """The single TSE-signed sale entry point. Idempotent on client_id."""
        existing = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.client_id == client_id)
        )).scalar_one_or_none()
        if existing:
            return existing

        order = (await self.db.execute(
            select(Order).where(Order.id == order_id)
        )).scalar_one()
        line_items = (await self.db.execute(
            select(LineItem).where(LineItem.order_id == order_id)
        )).scalars().all()

        vat_breakdown, total_net, total_gross = await self._build_vat_breakdown(line_items)

        receipt_number = (await self.db.execute(
            text("SELECT nextval('receipt_number_seq')")
        )).scalar_one()

        started_at = datetime.now(tz=timezone.utc)
        tx = PosTransaction(
            id=client_id,
            client_id=client_id,
            cashier_user_id=cashier_user_id,
            started_at=started_at,
            total_gross=total_gross,
            total_net=total_net,
            vat_breakdown={k: {kk: str(vv) for kk, vv in v.items()} for k, v in vat_breakdown.items()},
            payment_breakdown={k: str(v) for k, v in payment_breakdown.items()},
            receipt_number=receipt_number,
            linked_order_id=order_id,
            voids_transaction_id=voids_transaction_id,
            tse_pending=True,
        )
        self.db.add(tx)

        for li in line_items:
            line = _line_from_order_item(li, tx.id)
            self.db.add(line)
        await self.db.flush()

        process_data = build_process_data(
            vat_breakdown=vat_breakdown,
            payment_breakdown=dict(payment_breakdown),
        )
        try:
            start = await self.fiscal.start_transaction(client_id=client_id)
            finish = await self.fiscal.finish_transaction(
                tx_id=client_id,
                latest_revision=start.latest_revision,
                process_data=process_data,
            )
        except FiscalError:
            await self.db.commit()
            await self.db.refresh(tx)
            return tx

        await self.db.execute(text("SET LOCAL fiscal.signing = 'on'"))
        tx.tse_signature = finish.signature
        tx.tse_signature_counter = finish.signature_counter
        tx.tse_serial = finish.tss_serial
        tx.tse_timestamp_start = finish.time_start
        tx.tse_timestamp_finish = finish.time_end
        tx.tse_process_type = finish.process_type
        tx.tse_process_data = process_data
        tx.finished_at = datetime.now(tz=timezone.utc)
        tx.tse_pending = False
        await self.db.commit()
        await self.db.refresh(tx)
        return tx

    async def _build_vat_breakdown(
        self, line_items: list[LineItem],
    ) -> tuple[dict[str, dict[str, Decimal]], Decimal, Decimal]:
        """Day-1: single rate from default TaxRate. Plan D extends to multi-rate."""
        default_rate = (await self.db.execute(
            select(TaxRate).where(TaxRate.is_default.is_(True))
        )).scalar_one_or_none()
        rate = default_rate.rate if default_rate else Decimal("0")
        rate_pct = (rate * 100).quantize(Decimal("0.01"))
        slot = _rate_to_slot(rate_pct)

        total_gross = sum((_gross_for_line(li) for li in line_items), Decimal("0"))
        total_net = (total_gross / (1 + rate)).quantize(Decimal("0.01")) if rate else total_gross
        total_vat = (total_gross - total_net).quantize(Decimal("0.01"))

        return (
            {slot: {"net": total_net, "vat": total_vat, "gross": total_gross}},
            total_net,
            total_gross,
        )


_VAT_SLOT_BY_PCT = {
    Decimal("7.00"): "7",
    Decimal("19.00"): "19",
    Decimal("10.70"): "10.7",
    Decimal("0.00"): "0",
    Decimal("5.50"): "5.5",
}


def _rate_to_slot(rate_pct: Decimal) -> str:
    if rate_pct not in _VAT_SLOT_BY_PCT:
        raise ValueError(f"no DSFinV-K slot for VAT rate {rate_pct}")
    return _VAT_SLOT_BY_PCT[rate_pct]


def _gross_for_line(li: LineItem) -> Decimal:
    if li.quantity_kg is not None:
        return li.price
    return (li.price * li.quantity).quantize(Decimal("0.01"))


def _line_from_order_item(li: LineItem, pos_tx_id: uuid.UUID) -> PosTransactionLine:
    if li.quantity_kg is not None:
        line_total_gross = li.price
        qty = Decimal("1")
        unit_price = li.price / li.quantity_kg if li.quantity_kg else li.price
    else:
        unit_price = li.price
        qty = Decimal(li.quantity)
        line_total_gross = (li.price * li.quantity).quantize(Decimal("0.01"))

    return PosTransactionLine(
        pos_transaction_id=pos_tx_id,
        sku=None,
        title=li.title,
        quantity=qty,
        quantity_kg=li.quantity_kg,
        unit_price=unit_price.quantize(Decimal("0.0001")),
        line_total_net=line_total_gross,
        vat_rate=Decimal("0"),
        vat_amount=Decimal("0"),
    )
