"""Storno (correction) service — creates a signed negative PosTransaction."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.fiscal.errors import FiscalError
from app.fiscal.process_data import build_process_data
from app.models import PosTransaction, PosTransactionLine
from app.services.pos_transaction import PosTransactionService


class StornoService:
    def __init__(self, *, db: AsyncSession, pos_tx: PosTransactionService):
        self.db = db
        self.pos_tx = pos_tx

    async def void(
        self, *, original_id: uuid.UUID, cashier_user_id: int,
    ) -> PosTransaction:
        original = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.id == original_id)
        )).scalar_one()
        if original.voids_transaction_id is not None:
            raise ValueError("cannot void a Storno row itself")
        prior_void = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.voids_transaction_id == original_id)
        )).scalar_one_or_none()
        if prior_void:
            raise ValueError("transaction already voided")

        original_lines = (await self.db.execute(
            select(PosTransactionLine).where(
                PosTransactionLine.pos_transaction_id == original_id
            )
        )).scalars().all()

        cid = uuid.uuid4()
        receipt_number = (await self.db.execute(
            text("SELECT nextval('receipt_number_seq')")
        )).scalar_one()

        payment_breakdown = {
            k: -Decimal(v) for k, v in original.payment_breakdown.items()
        }
        vat_breakdown = {
            slot: {kk: str(-Decimal(vv)) for kk, vv in row.items()}
            for slot, row in original.vat_breakdown.items()
        }

        storno = PosTransaction(
            id=cid, client_id=cid,
            cashier_user_id=cashier_user_id,
            started_at=datetime.now(tz=timezone.utc),
            total_gross=-original.total_gross,
            total_net=-original.total_net,
            vat_breakdown=vat_breakdown,
            payment_breakdown={k: str(v) for k, v in payment_breakdown.items()},
            receipt_number=receipt_number,
            voids_transaction_id=original_id,
            tse_pending=True,
        )
        self.db.add(storno)
        for ln in original_lines:
            self.db.add(PosTransactionLine(
                pos_transaction_id=cid,
                sku=ln.sku, title=ln.title,
                quantity=-ln.quantity,
                quantity_kg=(-ln.quantity_kg) if ln.quantity_kg is not None else None,
                unit_price=ln.unit_price,
                line_total_net=-ln.line_total_net,
                vat_rate=ln.vat_rate,
                vat_amount=-ln.vat_amount,
            ))
        await self.db.flush()

        process_data = build_process_data(
            vat_breakdown={
                slot: {kk: Decimal(vv) for kk, vv in row.items()}
                for slot, row in vat_breakdown.items()
            },
            payment_breakdown=payment_breakdown,
        )
        try:
            start = await self.pos_tx.fiscal.start_transaction(client_id=cid)
            finish = await self.pos_tx.fiscal.finish_transaction(
                tx_id=cid, latest_revision=start.latest_revision,
                process_data=process_data,
            )
        except FiscalError:
            await self.db.commit()
            await self.db.refresh(storno)
            return storno

        await self.pos_tx.fiscal.apply_finish_to_pos_transaction(storno, finish, process_data=process_data)
        await self.db.commit()
        await self.db.refresh(storno)
        return storno
