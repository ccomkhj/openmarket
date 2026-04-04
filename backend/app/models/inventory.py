from sqlalchemy import Column, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, default="")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="CASCADE"), unique=True, nullable=False)
    cost = Column(Numeric(10, 2), nullable=True)

    variant = relationship("ProductVariant", back_populates="inventory_item")
    levels = relationship("InventoryLevel", back_populates="inventory_item", cascade="all, delete-orphan")


class InventoryLevel(Base):
    __tablename__ = "inventory_levels"
    __table_args__ = (
        Index("ix_inventory_levels_inventory_item_id", "inventory_item_id"),
        Index("ix_inventory_levels_location_id", "location_id"),
    )

    id = Column(Integer, primary_key=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    available = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=5)

    inventory_item = relationship("InventoryItem", back_populates="levels")
    location = relationship("Location")
