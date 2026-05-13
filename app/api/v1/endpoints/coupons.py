from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.coupon import Coupon, CouponUsage

router = APIRouter(prefix="/coupons", tags=["coupons"])


class CouponValidateRequest(BaseModel):
    code: str
    subtotal: float


class CouponValidateResponse(BaseModel):
    valid: bool
    discount_amount: float
    discount_type: str
    discount_value: float
    description: str | None = None
    message: str


@router.post("/validate", response_model=CouponValidateResponse)
async def validate_coupon(
    body: CouponValidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    code = body.code.upper().strip()

    result = await db.execute(
        select(Coupon).where(Coupon.code == code, Coupon.is_active == True)  # noqa: E712
    )
    coupon = result.scalar_one_or_none()

    if not coupon:
        raise HTTPException(status_code=400, detail="كود الخصم غير صحيح أو منتهي الصلاحية")

    if coupon.expires_at and coupon.expires_at < now:
        raise HTTPException(status_code=400, detail="انتهت صلاحية كود الخصم")

    if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        raise HTTPException(status_code=400, detail="تم استنفاد هذا الكود")

    if coupon.min_order_amount and body.subtotal < coupon.min_order_amount:
        raise HTTPException(
            status_code=400,
            detail=f"الحد الأدنى للطلب لاستخدام هذا الكود هو {coupon.min_order_amount:.0f} ر.ي"
        )

    usage_result = await db.execute(
        select(CouponUsage).where(
            CouponUsage.coupon_id == coupon.id,
            CouponUsage.user_id == current_user.id,
        )
    )
    if usage_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="لقد استخدمت هذا الكود من قبل")

    if coupon.discount_type == "percentage":
        discount = body.subtotal * (coupon.discount_value / 100)
    else:
        discount = coupon.discount_value

    if coupon.max_discount_amount:
        discount = min(discount, coupon.max_discount_amount)

    discount = round(discount, 2)
    return CouponValidateResponse(
        valid=True,
        discount_amount=discount,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        description=coupon.description,
        message=f"تم تطبيق الكوبون — خصم {discount:,.0f} ر.ي 🎉",
    )
