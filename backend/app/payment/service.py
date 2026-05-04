"""Cash + card sale orchestration."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, PosTransaction
from app.payment.terminal import PaymentTerminalBackend
from app.receipt.errors import ReceiptError
from app.receipt.service import ReceiptService
from app.services.pos_transaction import PosTransactionService

log = logging.getLogger(__name__)


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
        except (ReceiptError, OSError) as exc:
            log.warning("cash drawer pulse failed (sale succeeded): %s", exc)
        job = await self.receipts.print_receipt(tx.id)
        return PayResult(transaction=tx, change=change, receipt_status=job.status)

    async def pay_split(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
        cash_amount: Decimal,
        card_amount: Decimal,
    ) -> PayResult:
        """Settle one order with a cash + card split. One TSE-signed transaction,
        one receipt; payment_breakdown carries both tenders. Either side may be 0
        (in which case use pay_cash/pay_card directly), but both being zero is
        rejected and overpayment is not allowed."""
        from datetime import datetime, timezone
        from app.models import CardAuth
        from app.payment.errors import CardDeclinedError

        if cash_amount < 0 or card_amount < 0:
            raise ValueError("amounts must be non-negative")
        if cash_amount == 0 and card_amount == 0:
            raise ValueError("at least one tender amount must be > 0")

        total = await self._order_total(order_id)
        cash_q = cash_amount.quantize(Decimal("0.01"))
        card_q = card_amount.quantize(Decimal("0.01"))
        if (cash_q + card_q) != total:
            raise ValueError(
                f"split tendered {cash_q + card_q} != order total {total} (overpayment not allowed on split)"
            )

        # Authorize the card portion before we sign anything fiscally.
        card_auth = None
        if card_q > 0:
            try:
                card_auth = await self.terminal.authorize(amount=card_q)
            except CardDeclinedError as e:
                tx = await self.pos_tx.finalize_sale(
                    client_id=client_id, order_id=order_id,
                    cashier_user_id=cashier_user_id, payment_breakdown={},
                    cancelled_attempt=True,
                )
                self.db.add(CardAuth(
                    pos_transaction_id=tx.id, amount=card_q, approved=False,
                    response_code=str(getattr(e, "response_code", "")) or "decline",
                    auth_code="", trace_number="", terminal_id=self._terminal_id(),
                    created_at=datetime.now(tz=timezone.utc),
                ))
                await self.db.commit()
                raise

        breakdown: dict[str, Decimal] = {}
        if cash_q > 0:
            breakdown["cash"] = cash_q
        if card_q > 0:
            breakdown["girocard"] = card_q

        tx = await self.pos_tx.finalize_sale(
            client_id=client_id, order_id=order_id,
            cashier_user_id=cashier_user_id, payment_breakdown=breakdown,
        )

        if card_auth is not None:
            self.db.add(CardAuth(
                pos_transaction_id=tx.id, amount=card_q, approved=True,
                response_code=card_auth.response_code, auth_code=card_auth.auth_code,
                trace_number=card_auth.trace_number, terminal_id=card_auth.terminal_id,
                created_at=datetime.now(tz=timezone.utc),
            ))
            await self.db.commit()

        if cash_q > 0:
            try:
                self.receipts.backend.pulse_cash_drawer()
            except (ReceiptError, OSError) as exc:
                log.warning("cash drawer pulse failed (split sale succeeded): %s", exc)

        job = await self.receipts.print_receipt(tx.id)
        return PayResult(transaction=tx, change=Decimal("0"), receipt_status=job.status)

    async def pay_card(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
    ) -> PayResult:
        from datetime import datetime, timezone
        from app.models import CardAuth
        from app.payment.errors import CardDeclinedError

        total = await self._order_total(order_id)
        try:
            auth = await self.terminal.authorize(amount=total)
        except CardDeclinedError as e:
            tx = await self.pos_tx.finalize_sale(
                client_id=client_id, order_id=order_id,
                cashier_user_id=cashier_user_id, payment_breakdown={},
                cancelled_attempt=True,
            )
            self.db.add(CardAuth(
                pos_transaction_id=tx.id, amount=total, approved=False,
                response_code=str(getattr(e, "response_code", "")) or "decline",
                auth_code="", trace_number="", terminal_id=self._terminal_id(),
                created_at=datetime.now(tz=timezone.utc),
            ))
            await self.db.commit()
            raise

        tx = await self.pos_tx.finalize_sale(
            client_id=client_id, order_id=order_id, cashier_user_id=cashier_user_id,
            payment_breakdown={"girocard": total},
        )
        self.db.add(CardAuth(
            pos_transaction_id=tx.id, amount=total, approved=True,
            response_code=auth.response_code, auth_code=auth.auth_code,
            trace_number=auth.trace_number, terminal_id=auth.terminal_id,
            created_at=datetime.now(tz=timezone.utc),
        ))
        await self.db.commit()
        job = await self.receipts.print_receipt(tx.id)
        return PayResult(transaction=tx, receipt_status=job.status)

    def _terminal_id(self) -> str:
        return getattr(self.terminal, "host", "MOCK") + ":" + str(getattr(self.terminal, "port", "0"))
