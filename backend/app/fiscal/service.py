"""High-level fiskaly interactions: start/finish/retry."""
from __future__ import annotations

import base64
import time as _time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.fiscal.client import FiscalClient
from app.fiscal.errors import FiscalError
from app.models import PosTransaction, TseSigningLog


@dataclass
class StartResult:
    tx_id: uuid.UUID
    state: str
    latest_revision: int


@dataclass
class FinishResult:
    signature: str
    signature_counter: int
    tss_serial: str
    time_start: datetime
    time_end: datetime
    process_type: str


class FiscalService:
    def __init__(self, client: FiscalClient, db: Optional[AsyncSession] = None):
        self.client = client
        self.db = db

    async def _log(
        self, *,
        operation: str,
        pos_transaction_id: Optional[uuid.UUID],
        started_at: float,
        succeeded: bool,
        error: Optional[FiscalError] = None,
    ) -> None:
        if self.db is None:
            return
        self.db.add(TseSigningLog(
            pos_transaction_id=pos_transaction_id,
            operation=operation,
            attempted_at=datetime.now(tz=timezone.utc),
            succeeded=succeeded,
            error_code=error.error_code if error else None,
            error_message=str(error) if error else None,
            duration_ms=int((_time.time() - started_at) * 1000),
        ))
        await self.db.flush()

    async def start_transaction(self, *, client_id: uuid.UUID) -> StartResult:
        """Open a TSE transaction. The `client_id` is also the tx id on
        fiskaly's side — using the same UUID for both gives idempotency:
        retrying with the same id is safe.
        """
        started = _time.time()
        try:
            body = {"state": "ACTIVE", "client_id": str(client_id)}
            resp = await self.client.put(
                f"/api/v2/tss/{self.client.tss_id}/tx/{client_id}",
                json=body,
            )
            result = StartResult(
                tx_id=client_id,
                state=resp.get("state", "ACTIVE"),
                latest_revision=int(resp.get("latest_revision", 1)),
            )
        except FiscalError as e:
            await self._log(
                operation="start_transaction", pos_transaction_id=None,
                started_at=started, succeeded=False, error=e,
            )
            raise
        await self._log(
            operation="start_transaction", pos_transaction_id=None,
            started_at=started, succeeded=True,
        )
        return result

    async def finish_transaction(
        self, *,
        tx_id: uuid.UUID,
        latest_revision: int,
        process_data: str,
        process_type: str = "Kassenbeleg-V1",
    ) -> FinishResult:
        started = _time.time()
        try:
            body = {
                "state": "FINISHED",
                "client_id": str(tx_id),
                "schema": {
                    "standard_v1": {
                        "receipt": {
                            "receipt_type": "RECEIPT",
                            "amounts_per_vat_rate": [],
                            "amounts_per_payment_type": [],
                        },
                    },
                },
                "process_type": process_type,
                "process_data": _b64(process_data),
            }
            resp = await self.client.put(
                f"/api/v2/tss/{self.client.tss_id}/tx/{tx_id}?last_revision={latest_revision}",
                json=body,
            )
            sig = resp.get("signature") or {}
            result = FinishResult(
                signature=sig.get("value", ""),
                signature_counter=int(sig.get("counter", 0)),
                tss_serial=resp.get("tss_serial_number", ""),
                time_start=_utc_from_epoch(resp.get("time_start")),
                time_end=_utc_from_epoch(resp.get("time_end")),
                process_type=process_type,
            )
        except FiscalError as e:
            await self._log(
                operation="finish_transaction", pos_transaction_id=tx_id,
                started_at=started, succeeded=False, error=e,
            )
            raise
        await self._log(
            operation="finish_transaction", pos_transaction_id=tx_id,
            started_at=started, succeeded=True,
        )
        return result

    async def apply_finish_to_pos_transaction(self, tx, finish: FinishResult, process_data: str | None = None) -> None:
        """Apply fiskaly finish result to an in-flight PosTransaction row.
        Guarded by fiscal.signing=on session var — the single permitted
        mutation of a fiscal row. Caller owns the commit boundary.
        """
        if self.db is None:
            raise RuntimeError("apply_finish_to_pos_transaction requires db session")
        await self.db.execute(text("SET LOCAL fiscal.signing = 'on'"))
        tx.tse_signature = finish.signature
        tx.tse_signature_counter = finish.signature_counter
        tx.tse_serial = finish.tss_serial
        tx.tse_timestamp_start = finish.time_start
        tx.tse_timestamp_finish = finish.time_end
        tx.tse_process_type = finish.process_type
        if process_data is not None:
            tx.tse_process_data = process_data
        tx.finished_at = datetime.now(tz=timezone.utc)
        tx.tse_pending = False

    async def retry_pending_signatures(self) -> int:
        """Re-sign every PosTransaction with tse_pending=True. Returns count signed."""
        if self.db is None:
            raise RuntimeError("retry_pending_signatures requires db session")

        pending = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.tse_pending.is_(True)).limit(100)
        )).scalars().all()

        signed = 0
        for tx in pending:
            if not tx.tse_process_data:
                continue
            try:
                start = await self.start_transaction(client_id=tx.client_id)
                finish = await self.finish_transaction(
                    tx_id=tx.client_id,
                    latest_revision=start.latest_revision,
                    process_data=tx.tse_process_data,
                )
            except FiscalError:
                continue
            await self.apply_finish_to_pos_transaction(tx, finish)
            await self.db.commit()
            signed += 1
        return signed


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _utc_from_epoch(v: Any) -> datetime:
    if v is None:
        raise ValueError("missing timestamp in fiskaly response")
    return datetime.fromtimestamp(int(v), tz=timezone.utc)
