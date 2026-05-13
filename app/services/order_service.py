import uuid
import random
import string
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from app.models.order import Order, OrderItem, OrderStatus, OrderType
from app.models.payment import Payment, PaymentStatus, PaymentMethod
from app.models.merchant import Merchant
from app.models.product import Product, ProductStatus
from app.models.user import User
from app.models.address import Address
from app.models.coupon import Coupon, CouponUsage
import structlog

logger = structlog.get_logger()


def _generate_order_number() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"VOX-{suffix}"


async def _validate_coupon(
    db: AsyncSession, code: str, user_id, subtotal: float
) -> Tuple[float, Optional[str]]:
    """Returns (discount_amount, coupon_id_str). Raises ValueError if invalid."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Coupon).where(Coupon.code == code.upper().strip(), Coupon.is_active == True)  # noqa: E712
    )
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise ValueError("كود الخصم غير صحيح أو منتهي الصلاحية")

    if coupon.expires_at and coupon.expires_at < now:
        raise ValueError("انتهت صلاحية كود الخصم")

    if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        raise ValueError("تم استنفاد هذا الكود")

    if coupon.min_order_amount and subtotal < coupon.min_order_amount:
        raise ValueError(f"الحد الأدنى للطلب لاستخدام هذا الكود هو {coupon.min_order_amount:.0f} ر.ي")

    # Check if this user already used this coupon
    usage_result = await db.execute(
        select(CouponUsage).where(
            CouponUsage.coupon_id == coupon.id,
            CouponUsage.user_id == user_id,
        )
    )
    if usage_result.scalar_one_or_none():
        raise ValueError("لقد استخدمت هذا الكود من قبل")

    if coupon.discount_type == "percentage":
        discount = subtotal * (coupon.discount_value / 100)
    else:
        discount = coupon.discount_value

    if coupon.max_discount_amount:
        discount = min(discount, coupon.max_discount_amount)

    return round(discount, 2), str(coupon.id)


class OrderService:
    async def create_order(
        self,
        db: AsyncSession,
        customer: User,
        merchant_id: str,
        items_data: List[Dict],
        payment_method: str = "mock",
        address_id: Optional[str] = None,
        order_type: str = "delivery",
        delivery_notes: Optional[str] = None,
        coupon_code: Optional[str] = None,
        voice_session_id: Optional[str] = None,
        is_voice_order: bool = False,
    ) -> Order:
        merchant_result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
        merchant = merchant_result.scalar_one_or_none()
        if not merchant:
            raise ValueError("Merchant not found")

        address_data = None
        if address_id:
            addr_result = await db.execute(
                select(Address).where(Address.id == address_id, Address.user_id == customer.id)
            )
            address = addr_result.scalar_one_or_none()
            if address:
                address_data = {
                    "full_address": address.full_address,
                    "city": address.city,
                    "latitude": address.latitude,
                    "longitude": address.longitude,
                    "label": address.label,
                }

        order_items = []
        subtotal = 0.0

        for item_data in items_data:
            product_result = await db.execute(
                select(Product).where(
                    Product.id == item_data.get("product_id"),
                    Product.merchant_id == merchant_id,
                )
            )
            product = product_result.scalar_one_or_none()
            if not product:
                continue

            qty = item_data.get("quantity", 1)
            unit_price = product.effective_price
            item_total = unit_price * qty
            subtotal += item_total

            order_items.append(OrderItem(
                product_id=product.id,
                quantity=qty,
                unit_price=unit_price,
                total_price=item_total,
                notes=item_data.get("notes"),
                selected_options=item_data.get("selected_options"),
            ))

            product.total_orders += qty

        delivery_fee = merchant.delivery_fee
        if merchant.free_delivery_above and subtotal >= merchant.free_delivery_above:
            delivery_fee = 0.0

        discount = 0.0
        applied_coupon_id = None
        if coupon_code:
            try:
                discount, applied_coupon_id = await _validate_coupon(
                    db, coupon_code, customer.id, subtotal
                )
            except ValueError:
                raise

        tax = round(subtotal * 0.15, 2)
        total = subtotal + delivery_fee - discount + tax

        order = Order(
            order_number=_generate_order_number(),
            customer_id=customer.id,
            merchant_id=merchant.id,
            status=OrderStatus.PENDING,
            order_type=order_type,
            subtotal=round(subtotal, 2),
            delivery_fee=delivery_fee,
            discount_amount=discount,
            tax_amount=tax,
            total_amount=round(total, 2),
            delivery_address=address_data,
            delivery_notes=delivery_notes,
            estimated_delivery_time=merchant.avg_preparation_time + 20,
            is_voice_order=is_voice_order,
            voice_session_id=voice_session_id,
        )

        db.add(order)
        await db.flush()

        for item in order_items:
            item.order_id = order.id
            db.add(item)

        payment = Payment(
            order_id=order.id,
            amount=round(total, 2),
            method=payment_method,
            provider="mock" if payment_method == "mock" else payment_method,
            status=PaymentStatus.COMPLETED if payment_method in ("mock", "cash") else PaymentStatus.PENDING,
            provider_transaction_id=f"MOCK-{uuid.uuid4().hex[:12].upper()}" if payment_method == "mock" else None,
        )
        db.add(payment)

        merchant.total_orders += 1

        if applied_coupon_id:
            coupon_result = await db.execute(select(Coupon).where(Coupon.id == applied_coupon_id))
            used_coupon = coupon_result.scalar_one_or_none()
            if used_coupon:
                used_coupon.used_count += 1
                db.add(CouponUsage(
                    coupon_id=used_coupon.id,
                    user_id=customer.id,
                    order_id=order.id,
                ))

        await db.flush()
        await db.refresh(order)
        logger.info("order_created", order_id=str(order.id), order_number=order.order_number)
        return order

    async def create_voice_order(
        self,
        db: AsyncSession,
        customer: User,
        merchant_id: str,
        items: List[Dict],
        voice_session_id: str,
        payment_method: str = "mock",
        address_id: Optional[str] = None,
    ) -> Order:
        if not items:
            raise ValueError("No items in voice order")

        product_result = await db.execute(
            select(Product).where(
                Product.merchant_id == merchant_id,
                Product.status == ProductStatus.AVAILABLE,
            )
        )
        available_products = product_result.scalars().all()

        if not available_products:
            raise ValueError("No products available at this merchant")

        order_items_data = []
        for intent_item in items[:3]:
            item_name = (intent_item.get("name_en") or intent_item.get("name") or "").lower()
            best_match = None
            for p in available_products:
                product_name = (p.name or "").lower() + " " + (p.name_ar or "").lower()
                if any(word in product_name for word in item_name.split() if len(word) > 2):
                    best_match = p
                    break

            if not best_match:
                best_match = available_products[0]

            order_items_data.append({
                "product_id": str(best_match.id),
                "quantity": intent_item.get("quantity", 1),
                "notes": intent_item.get("notes"),
            })

        return await self.create_order(
            db=db,
            customer=customer,
            merchant_id=merchant_id,
            items_data=order_items_data,
            payment_method=payment_method,
            address_id=address_id,
            is_voice_order=True,
            voice_session_id=voice_session_id,
        )

    async def update_status(
        self,
        db: AsyncSession,
        order_id: str,
        new_status: str,
        actor: User,
    ) -> Order:
        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError("Order not found")

        order.status = new_status
        await db.flush()
        return order


order_service = OrderService()
