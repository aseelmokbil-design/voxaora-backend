import uuid
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class VoiceSession(Base, TimestampMixin):
    __tablename__ = "voice_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Audio / transcription
    audio_url = Column(String(500), nullable=True)
    transcript = Column(Text, nullable=True)
    transcript_language = Column(String(10), nullable=True)
    transcript_confidence = Column(Float, nullable=True)

    # Intent extraction
    raw_intent = Column(JSON, nullable=True)
    intent_category = Column(String(100), nullable=True)
    intent_items = Column(JSON, nullable=True)
    intent_constraints = Column(JSON, nullable=True)

    # Location at time of session
    user_latitude = Column(Float, nullable=True)
    user_longitude = Column(Float, nullable=True)

    # Results
    search_results = Column(JSON, nullable=True)
    selected_merchant_id = Column(UUID(as_uuid=True), nullable=True)

    # Outcome
    was_successful = Column(Boolean, default=False, nullable=False)
    processing_time_ms = Column(Integer, nullable=True)
    tts_response = Column(Text, nullable=True)

    user = relationship("User", back_populates="voice_sessions")
    order = relationship("Order", back_populates="voice_session", uselist=False,
                         primaryjoin="VoiceSession.id == foreign(Order.voice_session_id)")
