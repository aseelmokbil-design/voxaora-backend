import uuid
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class ProductStatus(str, PyEnum):
    AVAILABLE = "available"
    OUT_OF_STOCK = "out_of_stock"
    HIDDEN = "hidden"


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    name_ar = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    products = relationship("Product", back_populates="category", lazy="selectin")
    merchant = relationship("Merchant")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    name_ar = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    description_ar = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    discounted_price = Column(Float, nullable=True)
    image_url = Column(String(500), nullable=True)
    extra_images = Column(JSON, nullable=True)  # list of additional image URLs
    status = Column(String(30), default=ProductStatus.AVAILABLE, nullable=False)
    preparation_time = Column(Integer, default=15, nullable=False)
    calories = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)
    options = Column(JSON, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    total_orders = Column(Integer, default=0, nullable=False)
    rating = Column(Float, default=0.0, nullable=False)

    merchant = relationship("Merchant", back_populates="products")
    category = relationship("Category", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product", lazy="dynamic")

    @property
    def effective_price(self) -> float:
        return self.discounted_price if self.discounted_price else self.price
