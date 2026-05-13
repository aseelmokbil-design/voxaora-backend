import uuid
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Text, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class Deal(Base, TimestampMixin):
    __tablename__ = "deals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=True, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    title_ar = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    original_price = Column(Float, nullable=True)
    discounted_price = Column(Float, nullable=True)
    discount_pct = Column(Integer, nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    placement = Column(String(50), default="home", nullable=False)  # home | merchant | featured
    sort_order = Column(Integer, default=0, nullable=False)
    extra_images = Column(JSON, nullable=True)  # list of additional image URLs

    merchant = relationship("Merchant")


class Banner(Base, TimestampMixin):
    __tablename__ = "banners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=True)
    title_ar = Column(String(255), nullable=True)
    subtitle_ar = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=False)
    link_url = Column(String(500), nullable=True)
    placement = Column(String(50), default="home", nullable=False)  # home | merchant
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=True, index=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    bg_color = Column(String(50), nullable=True)  # optional gradient/bg color

    merchant = relationship("Merchant")
