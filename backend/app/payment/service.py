"""Cash + card sale orchestration."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, PosTransaction
from app.payment.terminal import PaymentTerminalBackend
from app.receipt.service import ReceiptService
from app.services.pos_transaction import PosTransactionService


@dataclass
class PayResult:
    transaction: PosTransaction
    change: Decimal = Decimal("0")
    receipt_status: str = "unknown"


class PaymentService:
    def __init__(
        self, *,
        db: AsyncSession,
        pos_tx: PosTransactionService,
        receipts: ReceiptService,
        terminal: PaymentTerminalBackend,
    ):
        self.db = db
        self.pos_tx = pos_tx
        self.receipts = receipts
        self.terminal = terminal

    async def _order_total(self, order_id: int) -> Decimal:
        order = (await self.db.execute(
            select(Order).where(Order.id == order_id)
        )).scalar_one()
        return Decimal(order.total_price)

    async def pay_cash(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
        tendered: Decimal,
    ) -> PayResult:
        total = await self._order_total(order_id)
        if tendered < total:
            raise ValueError(f"tendered {tendered} < total {total}")
        change = (tendered - total).quantize(Decimal("0.01"))
        tx = await self.pos_tx.finalize_sale(
            client_id=client_id, order_id=order_id, cashier_user_id=cashier_user_id,
            payment_breakdown={"cash": total},
        )
        try:
            self.receipts.backend.pulse_cash_drawer()
        except Exception:
            pass
        job = await self.receipts.print_receipt(tx.id)
        return PayResult(transaction=tx, change=change, receipt_status=job.status)

    async def pay_card(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
    ) -> PayResult:
        total = await self._order_total(order_id)
        auth = await self.terminal.authorize(amount=total)
        payment_breakdown = {"girocard": total}
        tx = await self.pos_tx.finalize_sale(
            client_id=client_id, order_id=order_id, cashier_user_id=cashier_user_id,
            payment_breakdown=payment_breakdown,
        )
        job = await self.receipts.print_receipt(tx.id)
        return PayResult(transaction=tx, receipt_status=job.status)
