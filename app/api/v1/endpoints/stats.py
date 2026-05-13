from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.core.database import get_db
from app.models.merchant import Merchant, MerchantStatus
from app.models.product import Product, ProductStatus, Category
from app.models.order import Order, OrderStatus
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/live")
async def live_stats(db: AsyncSession = Depends(get_db)):
    # Open merchants right now
    open_now = (await db.execute(
        select(func.count(Merchant.id)).where(
            Merchant.status == MerchantStatus.ACTIVE,
            Merchant.is_open_now == True,
        )
    )).scalar() or 0

    # Total active merchants
    total_merchants = (await db.execute(
        select(func.count(Merchant.id)).where(Merchant.status == MerchantStatus.ACTIVE)
    )).scalar() or 0

    # Total available products
    total_products = (await db.execute(
        select(func.count(Product.id)).where(Product.status == ProductStatus.AVAILABLE)
    )).scalar() or 0

    # Orders placed today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    orders_today = (await db.execute(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    )).scalar() or 0

    # Top 5 categories by product count
    cat_rows = (await db.execute(
        select(Category.name_ar, func.count(Product.id).label("cnt"))
        .join(Product, Product.category_id == Category.id)
        .where(Product.status == ProductStatus.AVAILABLE)
        .group_by(Category.name_ar)
        .order_by(desc("cnt"))
        .limit(5)
    )).all()
    top_categories = [{"name": r.name_ar, "count": r.cnt} for r in cat_rows]

    # Most ordered merchants today (social proof)
    hot_merchants_rows = (await db.execute(
        select(Merchant.name_ar, Merchant.id, func.count(Order.id).label("cnt"))
        .join(Order, Order.merchant_id == Merchant.id)
        .where(Order.created_at >= today_start - timedelta(days=7))
        .group_by(Merchant.id, Merchant.name_ar)
        .order_by(desc("cnt"))
        .limit(10)
    )).all()
    hot_merchants = {str(r.id): r.cnt for r in hot_merchants_rows}

    return {
        "open_now": open_now,
        "total_merchants": total_merchants,
        "total_products": total_products,
        "orders_today": orders_today,
        "top_categories": top_categories,
        "hot_merchants": hot_merchants,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
