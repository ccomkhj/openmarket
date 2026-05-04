from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class ParkedSale(Base):
    __tablename__ = "parked_sales"
    __table_args__ = (
        Index("ix_parked_sales_cashier", "cashier_user_id"),
        Index("ix_parked_sales_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    cashier_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id = Column(
        Integer,
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    items = Column(JSONB, nullable=False, server_default="[]")
    note = Column(String, nullable=False, server_default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cashier = relationship("User")
    customer = relationship("Customer")
