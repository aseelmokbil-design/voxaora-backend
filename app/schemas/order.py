from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = 1
    notes: Optional[str] = None
    selected_options: Optional[Dict[str, Any]] = None


class OrderCreate(BaseModel):
    merchant_id: UUID
    address_id: Optional[UUID] = None
    items: List[OrderItemCreate]
    order_type: str = "delivery"
    delivery_notes: Optional[str] = None
    coupon_code: Optional[str] = None
    payment_method: str = "mock"
    is_voice_order: bool = False
    voice_session_id: Optional[UUID] = None


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_name_ar: Optional[str]
    quantity: int
    unit_price: float
    total_price: float
    notes: Optional[str]
    image_url: Optional[str]

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: str
    order_number: str
    status: str
    order_type: str
    subtotal: float
    delivery_fee: float
    discount_amount: float
    tax_amount: float
    total_amount: float
    estimated_delivery_time: Optional[int]
    is_voice_order: bool
    items: List[OrderItemResponse]
    merchant: Optional[Dict[str, Any]]
    delivery_address: Optional[Dict[str, Any]]
    created_at: str

    class Config:
        from_attributes = True


class VoiceOrderRequest(BaseModel):
    voice_session_id: UUID
    selected_merchant_index: int = 0
    payment_method: str = "mock"
    address_id: Optional[UUID] = None
