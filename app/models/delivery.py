import uuid
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Float, ForeignKey, Integer, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class DeliveryStatus(str, PyEnum):
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    HEADING_TO_MERCHANT = "heading_to_merchant"
    AT_MERCHANT = "at_merchant"
    PICKED_UP = "picked_up"
    ON_THE_WAY = "on_the_way"
    NEAR_CUSTOMER = "near_customer"
    DELIVERED = "delivered"
    FAILED = "failed"


class Delivery(Base, TimestampMixin):
    __tablename__ = "deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(30), default=DeliveryStatus.ASSIGNED, nullable=False)

    pickup_latitude = Column(Float, nullable=True)
    pickup_longitude = Column(Float, nullable=True)
    dropoff_latitude = Column(Float, nullable=True)
    dropoff_longitude = Column(Float, nullable=True)

    distance_km = Column(Float, nullable=True)
    estimated_duration_minutes = Column(Integer, nullable=True)
    actual_duration_minutes = Column(Integer, nullable=True)

    driver_earnings = Column(Float, nullable=True)
    platform_fee = Column(Float, nullable=True)

    location_history = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)

    picked_up_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="delivery")
    driver = relationship("Driver", back_populates="deliveries")
