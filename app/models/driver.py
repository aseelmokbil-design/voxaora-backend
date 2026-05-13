import uuid
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class DriverStatus(str, PyEnum):
    OFFLINE = "offline"
    ONLINE = "online"
    BUSY = "busy"
    SUSPENDED = "suspended"


class Driver(Base, TimestampMixin):
    __tablename__ = "drivers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    vehicle_type = Column(String(50), nullable=False, default="motorcycle")
    vehicle_plate = Column(String(20), nullable=True)
    vehicle_model = Column(String(100), nullable=True)
    license_number = Column(String(100), nullable=True)
    status = Column(String(20), default=DriverStatus.OFFLINE, nullable=False, index=True)
    current_latitude = Column(Float, nullable=True)
    current_longitude = Column(Float, nullable=True)
    rating = Column(Float, default=0.0, nullable=False)
    total_deliveries = Column(Integer, default=0, nullable=False)
    total_earnings = Column(Float, default=0.0, nullable=False)
    city = Column(String(100), nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    orders = relationship("Order", back_populates="driver", lazy="dynamic")
    deliveries = relationship("Delivery", back_populates="driver", lazy="dynamic")
