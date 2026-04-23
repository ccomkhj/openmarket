"""Fiscal transaction models — append-only, DB-trigger-enforced."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PosTransaction(Base):
    __tablename__ = "pos_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    cashier_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    total_gross: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    total_net: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    vat_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    payment_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    receipt_number: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    linked_order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    voids_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), nullable=True,
    )

    tse_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tse_signature_counter: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tse_serial: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tse_timestamp_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tse_timestamp_finish: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tse_process_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tse_process_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tse_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    lines: Mapped[list["PosTransactionLine"]] = relationship(
        "PosTransactionLine", back_populates="transaction", cascade=None,
    )


class PosTransactionLine(Base):
    __tablename__ = "pos_transaction_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pos_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), nullable=False,
    )
    sku: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    quantity_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    line_total_net: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))

    transaction: Mapped["PosTransaction"] = relationship("PosTransaction", back_populates="lines")


class TseSigningLog(Base):
    __tablename__ = "tse_signing_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pos_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), nullable=True,
    )
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
