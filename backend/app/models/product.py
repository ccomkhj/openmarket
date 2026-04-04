from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_product_type", "product_type"),
        Index("ix_products_status", "status"),
    )

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    handle = Column(String, unique=True, nullable=False)
    description = Column(Text, default="")
    product_type = Column(String, default="")
    status = Column(String, default="active")
    tags = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        Index("ix_product_variants_barcode", "barcode"),
        Index("ix_product_variants_sku", "sku"),
        Index("ix_product_variants_product_id", "product_id"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, default="Default")
    sku = Column(String, default="")
    barcode = Column(String, default="")
    price = Column(Numeric(10, 2), nullable=False)
    compare_at_price = Column(Numeric(10, 2), nullable=True)
    position = Column(Integer, default=0)

    product = relationship("Product", back_populates="variants")
    inventory_item = relationship("InventoryItem", back_populates="variant", uselist=False, cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        Index("ix_product_images_product_id", "product_id"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    src = Column(String, nullable=False)
    position = Column(Integer, default=0)

    product = relationship("Product", back_populates="images")
