from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from app.core.database import get_db
from app.api.v1.deps import get_current_user, require_merchant, require_admin
from app.models.user import User, UserRole
from app.models.order import Order, OrderStatus
from app.models.notification import Notification, NotificationType
from app.schemas.order import OrderCreate, OrderResponse, OrderItemResponse
from app.services.order_service import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


def _serialize_order(order: Order) -> dict:
    items = [
        {
            "id": str(i.id),
            "product_id": str(i.product_id),
            "product_name": i.product.name if i.product else "",
            "product_name_ar": i.product.name_ar if i.product else None,
            "quantity": i.quantity,
            "unit_price": i.unit_price,
            "total_price": i.total_price,
            "notes": i.notes,
            "image_url": i.product.image_url if i.product else None,
        }
        for i in (order.items or [])
    ]
    merchant_data = None
    if order.merchant:
        merchant_data = {
            "id": str(order.merchant.id),
            "name": order.merchant.name,
            "name_ar": order.merchant.name_ar,
            "logo_url": order.merchant.logo_url,
            "phone": order.merchant.phone,
        }
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "status": order.status,
        "order_type": order.order_type,
        "subtotal": order.subtotal,
        "delivery_fee": order.delivery_fee,
        "discount_amount": order.discount_amount,
        "tax_amount": order.tax_amount,
        "total_amount": order.total_amount,
        "estimated_delivery_time": order.estimated_delivery_time,
        "is_voice_order": order.is_voice_order,
        "items": items,
        "merchant": merchant_data,
        "delivery_address": order.delivery_address,
        "delivery_notes": order.delivery_notes,
        "customer_rating": order.customer_rating,
        "customer_review": order.customer_review,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items_data = [
        {
            "product_id": str(i.product_id),
            "quantity": i.quantity,
            "notes": i.notes,
            "selected_options": i.selected_options,
        }
        for i in payload.items
    ]
    order = await order_service.create_order(
        db=db,
        customer=current_user,
        merchant_id=str(payload.merchant_id),
        items_data=items_data,
        payment_method=payload.payment_method,
        address_id=str(payload.address_id) if payload.address_id else None,
        order_type=payload.order_type,
        delivery_notes=payload.delivery_notes,
        coupon_code=payload.coupon_code,
        voice_session_id=str(payload.voice_session_id) if payload.voice_session_id else None,
        is_voice_order=payload.is_voice_order,
    )
    return _serialize_order(order)


@router.get("", response_model=List[dict])
async def list_orders(
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Order).where(Order.customer_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.order_by(desc(Order.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    orders = result.scalars().all()
    return [_serialize_order(o) for o in orders]


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if (
        str(order.customer_id) != str(current_user.id)
        and str(current_user.role) not in ("admin", "super_admin", "merchant", "driver")
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    return _serialize_order(order)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(order.customer_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    if str(order.status) not in (OrderStatus.PENDING.value, OrderStatus.CONFIRMED.value):
        raise HTTPException(status_code=400, detail="Cannot cancel order in current status")

    order.status = OrderStatus.CANCELLED

    notif = Notification(
        user_id=current_user.id,
        type=NotificationType.ORDER_CANCELLED,
        title="Order Cancelled",
        title_ar="تم إلغاء الطلب",
        body=f"Order #{order.order_number} has been cancelled.",
        body_ar=f"تم إلغاء طلبك رقم #{order.order_number}.",
        data={"order_id": str(order.id), "order_number": order.order_number},
    )
    db.add(notif)

    return {"message": "Order cancelled", "order_number": order.order_number}


@router.post("/{order_id}/rate")
async def rate_order(
    order_id: str,
    rating: int = Body(..., ge=1, le=5),
    review: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if str(order.customer_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    if str(order.status) != OrderStatus.DELIVERED.value:
        raise HTTPException(status_code=400, detail="يمكن تقييم الطلبات المكتملة فقط")
    if order.customer_rating is not None:
        raise HTTPException(status_code=400, detail="لقد قيّمت هذا الطلب مسبقاً")

    order.customer_rating = rating
    order.customer_review = review
    return {"ok": True, "rating": rating}


_STATUS_NOTIF = {
    "confirmed":        ("order_confirmed",  "تم قبول طلبك ✅",         "تم تأكيد طلبك ويجري التحضير الآن."),
    "preparing":        ("order_preparing",  "يجري تحضير طلبك 👨‍🍳",    "المطبخ يعمل على طلبك."),
    "ready_for_pickup": ("order_ready",      "طلبك جاهز 📦",             "تم تجهيز طلبك في انتظار السائق."),
    "picked_up":        ("order_picked_up",  "السائق في الطريق إليك 🛵", "تتبّع طلبك مباشرةً."),
    "on_the_way":       ("order_picked_up",  "السائق اقترب منك 🛵",      "سيصل طلبك قريباً."),
    "delivered":        ("order_delivered",  "وصل طلبك! بالعافية 🎉",    "نتمنى أن يعجبك. قيّم تجربتك."),
    "cancelled":        ("order_cancelled",  "تم إلغاء الطلب ❌",        "تم إلغاء طلبك."),
    "rejected":         ("order_cancelled",  "تم رفض الطلب 🚫",          "المتجر غير قادر على تلبية طلبك الآن."),
}


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: str,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_merchant),
):
    order = await order_service.update_status(db, order_id, new_status, current_user)

    notif_info = _STATUS_NOTIF.get(new_status)
    if notif_info:
        ntype, title_ar, body_ar = notif_info
        notif = Notification(
            user_id=order.customer_id,
            type=ntype,
            title=title_ar,
            title_ar=title_ar,
            body=body_ar,
            body_ar=body_ar,
            data={"order_id": str(order.id), "order_number": order.order_number},
        )
        db.add(notif)

    return {"message": "Status updated", "status": order.status}
