from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    handle = Column(String, unique=True, nullable=False)
    collection_type = Column(String, default="manual")
    rules = Column(JSON, nullable=True)

    products = relationship("CollectionProduct", back_populates="collection", cascade="all, delete-orphan")


class CollectionProduct(Base):
    __tablename__ = "collection_products"

    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    position = Column(Integer, default=0)

    collection = relationship("Collection", back_populates="products")
    product = relationship("Product")
