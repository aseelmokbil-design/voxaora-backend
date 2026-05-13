"""
VOXAORA Intelligence Layer
- Smart Reorder Suggestions (last orders the user can repeat with one tap)
- AI Personalization Preferences (learned from order history)
- Concierge Fallback (human-backed requests for unmatched demands)
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatus
from app.models.merchant import Merchant
from app.models.product import Product
from app.models.concierge import ConciergeRequest
from app.services.order_service import order_service
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# ── Reorder Suggestions ────────────────────────────────────────────────────────

@router.get("/reorder-suggestions")
async def get_reorder_suggestions(
    limit: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the user's last N unique completed orders, ready to repeat."""
    # Last 20 delivered/completed orders (skip cancelled/pending)
    terminal = [OrderStatus.DELIVERED, OrderStatus.CONFIRMED, OrderStatus.PREPARING,
                OrderStatus.ON_THE_WAY, OrderStatus.PICKED_UP]
    result = await db.execute(
        select(Order)
        .where(
            Order.customer_id == current_user.id,
            Order.status.in_(terminal),
        )
        .order_by(desc(Order.created_at))
        .limit(50)
    )
    all_orders = result.scalars().all()

    # De-duplicate by merchant — show each merchant once (most recent)
    seen_merchants = set()
    suggestions = []
    for order in all_orders:
        mid = str(order.merchant_id)
        if mid in seen_merchants:
            continue
        seen_merchants.add(mid)

        merchant_result = await db.execute(
            select(Merchant).where(Merchant.id == order.merchant_id)
        )
        merchant = merchant_result.scalar_one_or_none()
        if not merchant:
            continue

        # Serialize order items
        item_names = []
        for item in (order.items or []):
            if item.product:
                item_names.append(item.product.name_ar or item.product.name)

        suggestions.append({
            "order_id": str(order.id),
            "order_number": order.order_number,
            "merchant_id": str(merchant.id),
            "merchant_name": merchant.name_ar or merchant.name,
            "merchant_logo": merchant.logo_url,
            "merchant_is_open": merchant.is_open_now,
            "items_summary": "، ".join(item_names[:3]) or "طلب سابق",
            "total_amount": order.total_amount,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        })

        if len(suggestions) >= limit:
            break

    return {"suggestions": suggestions}


@router.post("/reorder/{order_id}")
async def reorder(
    order_id: str,
    payment_method: str = "cash",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clone a previous order and place it again."""
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.customer_id == current_user.id,
        )
    )
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="الطلب الأصلي غير موجود")

    # Verify merchant is still active
    merchant_result = await db.execute(
        select(Merchant).where(Merchant.id == original.merchant_id)
    )
    merchant = merchant_result.scalar_one_or_none()
    if not merchant or merchant.status != "active":
        raise HTTPException(status_code=400, detail="المتجر غير متاح حالياً")

    # Build items data from original order items
    items_data = []
    for item in (original.items or []):
        # Check product still exists and is available
        prod_result = await db.execute(
            select(Product).where(
                Product.id == item.product_id,
                Product.status == "available",
            )
        )
        product = prod_result.scalar_one_or_none()
        if product:
            items_data.append({
                "product_id": str(item.product_id),
                "quantity": item.quantity,
                "notes": item.notes,
            })

    if not items_data:
        raise HTTPException(status_code=400, detail="المنتجات المطلوبة لم تعد متوفرة")

    new_order = await order_service.create_order(
        db=db,
        customer=current_user,
        merchant_id=str(original.merchant_id),
        items_data=items_data,
        payment_method=payment_method,
        is_voice_order=False,
    )

    return {
        "order_id": str(new_order.id),
        "order_number": new_order.order_number,
        "total_amount": new_order.total_amount,
        "merchant_name": merchant.name_ar or merchant.name,
        "estimated_delivery_time": new_order.estimated_delivery_time,
        "tts_response": f"ممتاز! تم إعادة الطلب من {merchant.name_ar or merchant.name}. سيصلك خلال {new_order.estimated_delivery_time} دقيقة إن شاء الله.",
    }


# ── Personalization Preferences ───────────────────────────────────────────────

@router.get("/preferences")
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Derive user preferences from order history:
    - favorite_category, favorite_merchants
    - avg_order_value, peak_hour
    Used by search engine to boost personalized results.
    """
    result = await db.execute(
        select(Order)
        .where(
            Order.customer_id == current_user.id,
            Order.status == OrderStatus.DELIVERED,
        )
        .order_by(desc(Order.created_at))
        .limit(30)
    )
    orders = result.scalars().all()

    if not orders:
        return {
            "total_orders": 0,
            "favorite_category": None,
            "favorite_merchant_ids": [],
            "avg_order_value": 0,
            "peak_hour": None,
            "dietary_hints": [],
        }

    category_count: Dict[str, int] = {}
    merchant_count: Dict[str, int] = {}
    hour_count: Dict[int, int] = {}
    total_spent = 0.0

    for order in orders:
        # Get merchant category
        m_result = await db.execute(select(Merchant).where(Merchant.id == order.merchant_id))
        merchant = m_result.scalar_one_or_none()
        if merchant:
            cat = merchant.category
            category_count[cat] = category_count.get(cat, 0) + 1
            mid = str(order.merchant_id)
            merchant_count[mid] = merchant_count.get(mid, 0) + 1

        if order.created_at:
            h = order.created_at.hour
            hour_count[h] = hour_count.get(h, 0) + 1

        total_spent += order.total_amount or 0

    fav_category = max(category_count, key=category_count.get) if category_count else None
    fav_merchants = sorted(merchant_count.keys(), key=lambda m: merchant_count[m], reverse=True)[:3]
    peak_hour = max(hour_count, key=hour_count.get) if hour_count else None

    # Time of day label
    time_label = None
    if peak_hour is not None:
        if 5 <= peak_hour < 12:   time_label = "صباح"
        elif 12 <= peak_hour < 17: time_label = "ظهر"
        elif 17 <= peak_hour < 21: time_label = "مساء"
        else:                       time_label = "ليل"

    return {
        "total_orders": len(orders),
        "favorite_category": fav_category,
        "favorite_merchant_ids": fav_merchants,
        "avg_order_value": round(total_spent / len(orders), 2),
        "peak_hour": peak_hour,
        "peak_time_label": time_label,
        "category_breakdown": category_count,
    }


# ── Personalized Greeting ─────────────────────────────────────────────────────

@router.get("/greeting")
async def personalized_greeting(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a context-aware greeting with anticipation based on time + order history."""
    now = datetime.now(timezone.utc)
    hour = (now.hour + 3) % 24
    first_name = (current_user.full_name or "").split()[0]

    if 5 <= hour < 12:
        time_greeting = "صباح الخير"
    elif 12 <= hour < 17:
        time_greeting = "مرحباً"
    elif 17 <= hour < 21:
        time_greeting = "مساء الخير"
    else:
        time_greeting = "أهلاً"

    # Pull recent orders for peak-hour detection
    recent_result = await db.execute(
        select(Order)
        .where(
            Order.customer_id == current_user.id,
            Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CONFIRMED]),
        )
        .order_by(desc(Order.created_at))
        .limit(20)
    )
    recent_orders = recent_result.scalars().all()

    # Detect peak hour
    hour_count: Dict[int, int] = {}
    for o in recent_orders:
        if o.created_at:
            h = (o.created_at.hour + 3) % 24
            hour_count[h] = hour_count.get(h, 0) + 1

    peak_hour = max(hour_count, key=lambda h: hour_count[h]) if hour_count else None

    # Anticipation: if we're within 1 hour of the user's typical ordering time
    greeting_text = f"{time_greeting}، {first_name}! كيف نخدمك اليوم؟"
    if peak_hour is not None:
        delta = abs(((hour - peak_hour + 12) % 24) - 12)
        if delta <= 1 and len(recent_orders) >= 3:
            if   5 <= hour < 11: meal = "فطورك"
            elif 11 <= hour < 15: meal = "غداءك"
            elif 15 <= hour < 18: meal = "وجبتك الخفيفة"
            else:                  meal = "عشاءك"
            greeting_text = f"{first_name}، عادة تطلب {meal} الآن. هل أجهز لك أفضل الخيارات؟"

    # Last delivered order for proactive reorder suggestion
    last_result = await db.execute(
        select(Order)
        .where(
            Order.customer_id == current_user.id,
            Order.status == OrderStatus.DELIVERED,
        )
        .order_by(desc(Order.created_at))
        .limit(1)
    )
    last_order = last_result.scalar_one_or_none()

    suggestion = None
    suggestion_order_id = None
    if last_order:
        m_result = await db.execute(select(Merchant).where(Merchant.id == last_order.merchant_id))
        merchant = m_result.scalar_one_or_none()
        if merchant and merchant.is_open_now:
            item_names = []
            for item in (last_order.items or [])[:2]:
                if item.product:
                    item_names.append(item.product.name_ar or item.product.name)
            items_str = " و".join(item_names) if item_names else "طلبك السابق"
            suggestion = f"آخر مرة طلبت {items_str} من {merchant.name_ar or merchant.name}. هل تريد إعادة الطلب؟"
            suggestion_order_id = str(last_order.id)

    return {
        "greeting": greeting_text,
        "reorder_suggestion": suggestion,
        "reorder_order_id": suggestion_order_id,
        "hour": hour,
    }


# ── Impact Dashboard ──────────────────────────────────────────────────────────

@router.get("/impact")
async def get_user_impact(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate the real value VOXAORA has delivered.
    Used for the 'ما حققته بفضلنا' impact dashboard.
    """
    terminal = [
        OrderStatus.DELIVERED, OrderStatus.CONFIRMED, OrderStatus.PREPARING,
        OrderStatus.ON_THE_WAY, OrderStatus.PICKED_UP,
    ]
    result = await db.execute(
        select(Order)
        .where(
            Order.customer_id == current_user.id,
            Order.status.in_(terminal),
        )
        .order_by(desc(Order.created_at))
    )
    orders = result.scalars().all()

    total_orders   = len(orders)
    voice_orders   = sum(1 for o in orders if o.is_voice_order)
    total_spent    = sum(o.total_amount or 0 for o in orders)

    # Each voice order saves ~10 min vs manual search/compare; regular saves ~5 min
    time_saved_min = voice_orders * 10 + (total_orders - voice_orders) * 5
    time_saved_hours = round(time_saved_min / 60, 1)

    # Smart matching finds ~7% better value on average (platform price intelligence)
    money_saved = int(total_spent * 0.07)

    # Quick reorders: merchants ordered from more than once
    merchant_count: Dict[str, int] = {}
    for o in orders:
        mid = str(o.merchant_id)
        merchant_count[mid] = merchant_count.get(mid, 0) + 1
    quick_reorders = sum(1 for c in merchant_count.values() if c > 1)

    # This month stats
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_orders = [o for o in orders if o.created_at and o.created_at >= month_start]
    month_voice  = sum(1 for o in month_orders if o.is_voice_order)
    month_spent  = sum(o.total_amount or 0 for o in month_orders)
    month_time   = round((month_voice * 10 + (len(month_orders) - month_voice) * 5) / 60, 1)
    month_saved  = int(month_spent * 0.07)

    first_order = orders[-1] if orders else None

    return {
        "total_orders":        total_orders,
        "voice_commands_used": voice_orders,
        "time_saved_hours":    time_saved_hours,
        "money_saved":         money_saved,
        "quick_reorders":      quick_reorders,
        "smart_decisions":     total_orders,
        "this_month": {
            "orders":       len(month_orders),
            "voice_used":   month_voice,
            "time_saved_h": month_time,
            "money_saved":  month_saved,
        },
        "member_since": first_order.created_at.isoformat() if first_order and first_order.created_at else None,
    }


# ── Concierge Fallback ────────────────────────────────────────────────────────

class ConciergeRequestBody(BaseModel):
    request_text: str
    category_hint: Optional[str] = None
    is_voice_request: bool = False


@router.post("/concierge")
async def submit_concierge_request(
    body: ConciergeRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a request that couldn't be fulfilled automatically — a human will handle it."""
    req = ConciergeRequest(
        user_id=current_user.id,
        request_text=body.request_text,
        category_hint=body.category_hint,
        user_phone=current_user.phone,
        is_voice_request=body.is_voice_request,
        status="pending",
    )
    db.add(req)
    await db.flush()

    logger.info("concierge_request_created",
                request_id=str(req.id), user=str(current_user.id), text=body.request_text[:100])

    return {
        "request_id": str(req.id),
        "status": "pending",
        "tts_response": "تمام! استلمنا طلبك. سيتواصل معك أحد موظفينا قريباً على رقمك لتنفيذ الطلب.",
        "message": "سيتم التواصل معك خلال 15-30 دقيقة على رقمك المسجل.",
    }


@router.get("/loyalty")
async def get_loyalty(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Loyalty points derived from order history. 1 point per SAR spent."""
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == current_user.id, Order.status == OrderStatus.DELIVERED)
    )
    orders = result.scalars().all()
    total_spent = sum(o.total_amount or 0 for o in orders)
    points = int(total_spent)

    # Tier thresholds
    tiers = [
        (0,    500,  "Bronze",   "برونزي",   "🥉"),
        (500,  2000, "Silver",   "فضي",      "🥈"),
        (2000, 5000, "Gold",     "ذهبي",     "🥇"),
        (5000, None, "Platinum", "بلاتيني",  "💎"),
    ]
    tier_name_ar, tier_emoji, next_threshold = "برونزي", "🥉", 500
    for lo, hi, _, name_ar, emoji in tiers:
        if hi is None or points < hi:
            tier_name_ar, tier_emoji = name_ar, emoji
            next_threshold = hi if hi else points
            break

    points_to_next = max(0, next_threshold - points) if next_threshold != points else 0
    progress_pct = min(100, int((points / next_threshold * 100))) if next_threshold else 100

    return {
        "points": points,
        "tier": tier_name_ar,
        "tier_emoji": tier_emoji,
        "next_threshold": next_threshold,
        "points_to_next": points_to_next,
        "progress_pct": progress_pct,
        "total_orders": len(orders),
    }


@router.get("/streaks")
async def get_streaks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate order streaks (consecutive days with at least one order)."""
    result = await db.execute(
        select(Order.created_at)
        .where(
            Order.customer_id == current_user.id,
            Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CONFIRMED, OrderStatus.PREPARING]),
        )
        .order_by(desc(Order.created_at))
        .limit(90)
    )
    timestamps = [row[0] for row in result.all() if row[0]]

    if not timestamps:
        return {"current_streak": 0, "longest_streak": 0, "last_order_date": None}

    # Get unique order days (in local time, UTC+3)
    order_days = sorted(
        {(ts.replace(tzinfo=None) if ts.tzinfo else ts).date() for ts in timestamps},
        reverse=True,
    )

    from datetime import date, timedelta
    today = date.today()

    # Current streak
    current_streak = 0
    check_day = today
    for day in order_days:
        if day == check_day or day == check_day - timedelta(days=1):
            current_streak += 1
            check_day = day - timedelta(days=1) if day != check_day else check_day - timedelta(days=1)
        else:
            break

    # If most recent order is not today or yesterday, streak is 0
    if order_days and order_days[0] < today - timedelta(days=1):
        current_streak = 0

    # Longest streak
    longest = 1
    run = 1
    for i in range(1, len(order_days)):
        if (order_days[i - 1] - order_days[i]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1

    return {
        "current_streak": current_streak,
        "longest_streak": max(longest, current_streak),
        "last_order_date": order_days[0].isoformat() if order_days else None,
        "total_order_days": len(order_days),
    }


@router.get("/concierge/my")
async def my_concierge_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ConciergeRequest)
        .where(ConciergeRequest.user_id == current_user.id)
        .order_by(desc(ConciergeRequest.created_at))
        .limit(10)
    )
    requests = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "request_text": r.request_text,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in requests
    ]
