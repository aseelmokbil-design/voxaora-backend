import uuid
from sqlalchemy import Column, String, Float, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class DriverDocument(Base, TimestampMixin):
    __tablename__ = "driver_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(50), nullable=False)   # id_card | license | vehicle_front | vehicle_back | selfie
    file_url = Column(String(500), nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending | approved | rejected
    notes = Column(Text, nullable=True)

    driver = relationship("Driver", foreign_keys=[driver_id])


class DriverTransaction(Base, TimestampMixin):
    __tablename__ = "driver_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True)
    tx_type = Column(String(30), nullable=False)    # earning | bonus | deduction | withdrawal
    amount = Column(Float, nullable=False)          # positive = credit, negative = debit
    description = Column(String(255), nullable=False)
    status = Column(String(20), default="completed", nullable=False)  # completed | pending | cancelled
    reference_id = Column(String(100), nullable=True)   # order_id or bonus_id

    driver = relationship("Driver", foreign_keys=[driver_id])
