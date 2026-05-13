import uuid
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class ConciergeRequest(Base, TimestampMixin):
    __tablename__ = "concierge_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    request_text = Column(Text, nullable=False)
    category_hint = Column(String(100), nullable=True)
    user_phone = Column(String(30), nullable=True)
    status = Column(String(30), default="pending", nullable=False)   # pending, in_progress, resolved, cancelled
    resolution_notes = Column(Text, nullable=True)
    is_voice_request = Column(Boolean, default=False)

    user = relationship("User", foreign_keys=[user_id])
