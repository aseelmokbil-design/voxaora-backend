import uuid
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class OrderStatus(str, PyEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY_FOR_PICKUP = "ready_for_pickup"
    PICKED_UP = "picked_up"
    ON_THE_WAY = "on_the_way"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(str, PyEnum):
    DELIVERY = "delivery"
    PICKUP = "pickup"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    order_number = Column(String(20), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False, index=True)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True, index=True)
    address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True)
    voice_session_id = Column(UUID(as_uuid=True), ForeignKey("voice_sessions.id", ondelete="SET NULL"), nullable=True)
    coupon_id = Column(UUID(as_uuid=True), ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True)

    status = Column(String(30), default=OrderStatus.PENDING, nullable=False, index=True)
    order_type = Column(String(20), default=OrderType.DELIVERY, nullable=False)

    # Pricing
    subtotal = Column(Float, nullable=False)
    delivery_fee = Column(Float, default=0.0, nullable=False)
    discount_amount = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, nullable=False)

    # Delivery details
    delivery_address = Column(JSON, nullable=True)
    delivery_notes = Column(Text, nullable=True)
    estimated_delivery_time = Column(Integer, nullable=True)

    # Merchant notes
    preparation_time = Column(Integer, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Voice order flag
    is_voice_order = Column(Boolean, default=False, nullable=False)

    # Ratings
    customer_rating = Column(Integer, nullable=True)
    customer_review = Column(Text, nullable=True)

    items = relationship("OrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan")
    customer = relationship("User", back_populates="orders")
    merchant = relationship("Merchant", back_populates="orders")
    driver = relationship("Driver", back_populates="orders")
    payment = relationship("Payment", back_populates="order", uselist=False, lazy="selectin")
    delivery = relationship("Delivery", back_populates="order", uselist=False, lazy="selectin")
    voice_session = relationship("VoiceSession", back_populates="order", foreign_keys=[voice_session_id])


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    selected_options = Column(JSON, nullable=True)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
