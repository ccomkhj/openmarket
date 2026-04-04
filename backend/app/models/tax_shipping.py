from sqlalchemy import Boolean, Column, Integer, Numeric, String

from app.database import Base


class TaxRate(Base):
    __tablename__ = "tax_rates"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    rate = Column(Numeric(5, 4), nullable=False)  # e.g. 0.1000 for 10%
    region = Column(String, default="")
    is_default = Column(Boolean, default=False)


class ShippingMethod(Base):
    __tablename__ = "shipping_methods"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    min_order_amount = Column(Numeric(10, 2), default=0)  # free shipping threshold
    is_active = Column(Boolean, default=True)
