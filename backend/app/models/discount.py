from sqlalchemy import Column, DateTime, Integer, Numeric, String

from app.database import Base


class Discount(Base):
    __tablename__ = "discounts"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    discount_type = Column(String, nullable=False)
    value = Column(Numeric(10, 2), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
