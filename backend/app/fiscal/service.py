"""High-level fiskaly interactions: start/finish/retry."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.fiscal.client import FiscalClient


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
    def __init__(self, client: FiscalClient):
        self.client = client

    async def start_transaction(self, *, client_id: uuid.UUID) -> StartResult:
        """Open a TSE transaction. The `client_id` is also the tx id on
        fiskaly's side — using the same UUID for both gives idempotency:
        retrying with the same id is safe.
        """
        body = {"state": "ACTIVE", "client_id": str(client_id)}
        resp = await self.client.put(
            f"/api/v2/tss/{self.client.tss_id}/tx/{client_id}",
            json=body,
        )
        return StartResult(
            tx_id=client_id,
            state=resp.get("state", "ACTIVE"),
            latest_revision=int(resp.get("latest_revision", 1)),
        )
