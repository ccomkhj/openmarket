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
from app.fiscal.vat import VAT_SLOT_BY_PCT
from app.models import (
    LineItem, PosTransaction, PosTransactionLine, TaxRate,
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
        cancelled_attempt: bool = False,
    ) -> PosTransaction:
        """The single TSE-signed sale entry point. Idempotent on client_id."""
        existing = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.client_id == client_id)
        )).scalar_one_or_none()
        if existing:
            return existing

        line_items = (await self.db.execute(
            select(LineItem).where(LineItem.order_id == order_id)
        )).scalars().all()

        if cancelled_attempt:
            vat_breakdown: dict[str, dict[str, Decimal]] = {}
            total_net = Decimal("0")
            total_gross = Decimal("0")
        else:
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

        if not cancelled_attempt:
            from app.models import ProductVariant
            variants = (await self.db.execute(
                select(ProductVariant).where(ProductVariant.id.in_([li.variant_id for li in line_items]))
            )).scalars().all()
            by_id = {v.id: v for v in variants}

            for li in line_items:
                line = _line_from_order_item(li, tx.id, by_id[li.variant_id])
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

        await self.fiscal.apply_finish_to_pos_transaction(tx, finish, process_data=process_data)
        await self.db.commit()
        await self.db.refresh(tx)
        return tx

    async def _build_vat_breakdown(
        self, line_items,
    ) -> tuple[dict[str, dict[str, Decimal]], Decimal, Decimal]:
        from app.models import ProductVariant
        from app.fiscal.vat import VAT_SLOT_BY_PCT
        variant_ids = [li.variant_id for li in line_items]
        variants = (await self.db.execute(
            select(ProductVariant).where(ProductVariant.id.in_(variant_ids))
        )).scalars().all()
        by_id = {v.id: v for v in variants}

        slots: dict[str, dict[str, Decimal]] = {}
        total_gross = Decimal("0")
        total_net = Decimal("0")
        for li in line_items:
            v = by_id[li.variant_id]
            rate_pct = Decimal(v.vat_rate).quantize(Decimal("0.01"))
            slot = _rate_to_slot(rate_pct)
            gross = _gross_for_line(li)
            rate_frac = rate_pct / Decimal("100")
            net = (gross / (1 + rate_frac)).quantize(Decimal("0.01"))
            vat = (gross - net).quantize(Decimal("0.01"))
            cur = slots.setdefault(slot, {"net": Decimal("0"), "vat": Decimal("0"), "gross": Decimal("0")})
            cur["net"] += net
            cur["vat"] += vat
            cur["gross"] += gross
            total_gross += gross
            total_net += net
        return slots, total_net, total_gross


def _rate_to_slot(rate_pct: Decimal) -> str:
    if rate_pct not in VAT_SLOT_BY_PCT:
        raise ValueError(f"no DSFinV-K slot for VAT rate {rate_pct}")
    return VAT_SLOT_BY_PCT[rate_pct]


def _gross_for_line(li: LineItem) -> Decimal:
    if li.quantity_kg is not None:
        return li.price
    return (li.price * li.quantity).quantize(Decimal("0.01"))


def _line_from_order_item(li, pos_tx_id: uuid.UUID, variant) -> PosTransactionLine:
    line_total_gross = _gross_for_line(li)
    rate_pct = Decimal(variant.vat_rate).quantize(Decimal("0.01"))
    rate_frac = rate_pct / Decimal("100")
    line_net = (line_total_gross / (1 + rate_frac)).quantize(Decimal("0.01"))
    line_vat = (line_total_gross - line_net).quantize(Decimal("0.01"))

    if li.quantity_kg is not None:
        qty = Decimal("1")
        unit_price = li.price / li.quantity_kg
    else:
        qty = Decimal(li.quantity)
        unit_price = li.price

    return PosTransactionLine(
        pos_transaction_id=pos_tx_id,
        sku=variant.sku,
        title=li.title,
        quantity=qty,
        quantity_kg=li.quantity_kg,
        unit_price=unit_price.quantize(Decimal("0.0001")),
        line_total_net=line_net,
        vat_rate=rate_pct,
        vat_amount=line_vat,
    )
