import uuid
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Float, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class PaymentStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, PyEnum):
    CASH = "cash"
    CARD = "card"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    WALLET = "wallet"
    MOCK = "mock"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="SAR", nullable=False)
    status = Column(String(30), default=PaymentStatus.PENDING, nullable=False, index=True)
    method = Column(String(30), nullable=False)
    provider = Column(String(50), default="mock", nullable=False)
    provider_transaction_id = Column(String(255), nullable=True, unique=True)
    provider_response = Column(JSON, nullable=True)
    refund_amount = Column(Float, nullable=True)
    failure_reason = Column(Text, nullable=True)

    order = relationship("Order", back_populates="payment")
