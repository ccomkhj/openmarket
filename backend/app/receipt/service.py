"""Bind a PosTransaction to a physical print + a ReceiptPrintJob row."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PosTransaction, PosTransactionLine, ReceiptPrintJob,
)
from app.receipt.builder import ReceiptBuilder
from app.receipt.errors import (
    PrinterPaperOutError, PrinterUnavailableError, PrinterWriteError, ReceiptError,
)
from app.receipt.printer import PrinterBackend


class ReceiptService:
    def __init__(
        self, *,
        db: AsyncSession,
        builder: ReceiptBuilder,
        backend: PrinterBackend,
    ):
        self.db = db
        self.builder = builder
        self.backend = backend

    async def print_receipt(self, pos_transaction_id: uuid.UUID) -> ReceiptPrintJob:
        """Create a new print job and attempt printing (used for both first print and reprint)."""
        return await self._print(pos_transaction_id)

    async def _print(self, pos_transaction_id: uuid.UUID) -> ReceiptPrintJob:
        tx, lines = await self._load(pos_transaction_id)
        data = self.builder.render(tx, lines)
        job = ReceiptPrintJob(
            pos_transaction_id=pos_transaction_id,
            status="pending", attempts=0,
            created_at=datetime.now(tz=timezone.utc),
        )
        self.db.add(job)
        await self.db.flush()
        return await self._attempt(job, data)

    async def _attempt(self, job: ReceiptPrintJob, data: bytes) -> ReceiptPrintJob:
        job.attempts = job.attempts + 1
        try:
            self.backend.write(data)
        except (PrinterPaperOutError, PrinterUnavailableError, PrinterWriteError) as e:
            job.status = "buffered"
            job.last_error = str(e)
            await self.db.commit()
            await self.db.refresh(job)
            return job
        except ReceiptError as e:
            job.status = "failed"
            job.last_error = str(e)
            await self.db.commit()
            await self.db.refresh(job)
            return job

        job.status = "printed"
        job.printed_at = datetime.now(tz=timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def _load(self, pos_transaction_id: uuid.UUID):
        tx = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.id == pos_transaction_id)
        )).scalar_one()
        lines = (await self.db.execute(
            select(PosTransactionLine).where(PosTransactionLine.pos_transaction_id == pos_transaction_id)
        )).scalars().all()
        return tx, lines
