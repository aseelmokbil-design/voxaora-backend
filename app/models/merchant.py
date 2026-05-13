import uuid
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Text, Integer, Time, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class MerchantStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_APPROVAL = "pending_approval"


class MerchantCategory(str, PyEnum):
    RESTAURANT = "restaurant"
    GROCERY = "grocery"
    PHARMACY = "pharmacy"
    COFFEE = "coffee"
    BAKERY = "bakery"
    ELECTRONICS = "electronics"
    SERVICES = "services"
    OTHER = "other"


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    name_ar = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    description_ar = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)
    logo_url = Column(String(500), nullable=True)
    cover_image_url = Column(String(500), nullable=True)
    status = Column(String(30), default=MerchantStatus.PENDING_APPROVAL, nullable=False)
    rating = Column(Float, default=0.0, nullable=False)
    total_reviews = Column(Integer, default=0, nullable=False)
    total_orders = Column(Integer, default=0, nullable=False)

    # Location
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    full_address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    district = Column(String(100), nullable=True)

    # Delivery settings
    delivery_radius_km = Column(Float, default=5.0, nullable=False)
    min_order_amount = Column(Float, default=0.0, nullable=False)
    delivery_fee = Column(Float, default=0.0, nullable=False)
    free_delivery_above = Column(Float, nullable=True)
    avg_preparation_time = Column(Integer, default=20, nullable=False)

    # Operating hours (JSON array of {day, open, close, is_closed})
    operating_hours = Column(JSON, nullable=True)
    is_open_now = Column(Boolean, default=True, nullable=False)

    # Business info
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    tax_number = Column(String(100), nullable=True)
    commission_rate = Column(Float, default=15.0, nullable=False)

    products = relationship("Product", back_populates="merchant", lazy="dynamic")
    orders = relationship("Order", back_populates="merchant", lazy="dynamic")
    reviews = relationship("Review", back_populates="merchant", lazy="dynamic")
    owner = relationship("User", foreign_keys=[owner_id])
