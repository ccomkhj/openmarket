from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CardAuth(Base):
    __tablename__ = "card_auths"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pos_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), unique=True, nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    response_code: Mapped[str] = mapped_column(Text, nullable=False)
    auth_code: Mapped[str] = mapped_column(Text, nullable=False)
    trace_number: Mapped[str] = mapped_column(Text, nullable=False)
    terminal_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
