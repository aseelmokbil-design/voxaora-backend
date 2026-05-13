import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class UserRole(str, PyEnum):
    CUSTOMER = "customer"
    MERCHANT = "merchant"
    DRIVER = "driver"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class UserStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(30), default=UserRole.CUSTOMER.value, nullable=False)
    status = Column(String(30), default=UserStatus.ACTIVE.value, nullable=False)
    profile_image_url = Column(String(500), nullable=True)
    preferred_language = Column(String(10), default="ar", nullable=False)
    fcm_token = Column(String(500), nullable=True)
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    addresses = relationship("Address", back_populates="user", lazy="selectin")
    orders = relationship("Order", back_populates="customer", lazy="dynamic")
    voice_sessions = relationship("VoiceSession", back_populates="user", lazy="dynamic")
    notifications = relationship("Notification", back_populates="user", lazy="dynamic")
    reviews = relationship("Review", back_populates="user", lazy="dynamic")
