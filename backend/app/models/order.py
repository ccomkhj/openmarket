from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Return(Base):
    __tablename__ = "returns"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    reason = Column(String, default="")
    total_refund = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    order = relationship("Order")
    items = relationship("ReturnItem", back_populates="return_record", cascade="all, delete-orphan")


class ReturnItem(Base):
    __tablename__ = "return_items"
    id = Column(Integer, primary_key=True)
    return_id = Column(Integer, ForeignKey("returns.id", ondelete="CASCADE"), nullable=False)
    line_item_id = Column(Integer, ForeignKey("line_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    return_record = relationship("Return", back_populates="items")
    line_item = relationship("LineItem")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String, unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    source = Column(String, nullable=False)
    fulfillment_status = Column(String, default="unfulfilled")
    subtotal = Column(Numeric(10, 2), nullable=False, default=0)
    tax_amount = Column(Numeric(10, 2), default=0)
    shipping_amount = Column(Numeric(10, 2), default=0)
    total_price = Column(Numeric(10, 2), nullable=False)
    shipping_address = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer")
    line_items = relationship("LineItem", back_populates="order", cascade="all, delete-orphan")
    fulfillments = relationship("Fulfillment", back_populates="order", cascade="all, delete-orphan")


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    title = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="line_items")
    variant = relationship("ProductVariant")


class Fulfillment(Base):
    __tablename__ = "fulfillments"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="fulfillments")
