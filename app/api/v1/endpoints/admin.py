import os
import uuid
import shutil
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, and_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.api.v1.deps import require_admin
from app.models.user import User, UserStatus, UserRole
from app.models.merchant import Merchant, MerchantStatus
from app.models.order import Order, OrderStatus
from app.models.driver import Driver
from app.models.product import Product, ProductStatus, Category
from app.models.deals import Deal, Banner
from app.core.security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])

UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


# ─── Pydantic models ──────────────────────────────────────────────────────────

class MerchantApprove(BaseModel):
    merchant_id: str
    action: str  # approve | reject | suspend


class UserAction(BaseModel):
    user_id: str
    action: str  # suspend | activate


class MerchantUpdate(BaseModel):
    name: Optional[str] = None
    name_ar: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    phone: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    delivery_fee: Optional[float] = None
    min_order_amount: Optional[float] = None
    avg_preparation_time: Optional[int] = None
    is_open_now: Optional[bool] = None
    operating_hours: Optional[list] = None
    status: Optional[str] = None


class ProductCreate(BaseModel):
    name: str
    name_ar: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    price: float
    discounted_price: Optional[float] = None
    image_url: Optional[str] = None
    extra_images: Optional[list] = None
    status: str = "available"
    preparation_time: int = 15
    calories: Optional[int] = None
    tags: Optional[list] = None
    category_id: Optional[str] = None
    sort_order: int = 0


class ProductUpdate(ProductCreate):
    name: Optional[str] = None
    price: Optional[float] = None


class CategoryCreate(BaseModel):
    name: str
    name_ar: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class DealCreate(BaseModel):
    title: str
    title_ar: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    original_price: Optional[float] = None
    discounted_price: Optional[float] = None
    discount_pct: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True
    placement: str = "home"
    merchant_id: Optional[str] = None
    product_id: Optional[str] = None
    sort_order: int = 0
    extra_images: Optional[list] = None


class DealUpdate(DealCreate):
    title: Optional[str] = None


class BannerCreate(BaseModel):
    title: Optional[str] = None
    title_ar: Optional[str] = None
    subtitle_ar: Optional[str] = None
    image_url: str
    link_url: Optional[str] = None
    placement: str = "home"
    merchant_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True
    sort_order: int = 0
    bg_color: Optional[str] = None


class BannerUpdate(BannerCreate):
    image_url: Optional[str] = None


# ─── Image upload ─────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}")

    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOADS_DIR, filename)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"url": f"/uploads/{filename}", "filename": filename}


# ─── Dashboard ───────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    total_users = (await db.execute(func.count(User.id))).scalar()
    total_merchants = (await db.execute(func.count(Merchant.id))).scalar()
    total_orders = (await db.execute(func.count(Order.id))).scalar()
    active_drivers = (await db.execute(
        select(func.count(Driver.id)).where(Driver.status == "online")
    )).scalar()

    pending_orders = (await db.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)
    )).scalar()

    revenue_result = await db.execute(
        select(func.sum(Order.total_amount)).where(Order.status == OrderStatus.DELIVERED)
    )
    total_revenue = revenue_result.scalar() or 0.0

    pending_merchants = (await db.execute(
        select(func.count(Merchant.id)).where(Merchant.status == MerchantStatus.PENDING_APPROVAL)
    )).scalar()

    active_deals = (await db.execute(
        select(func.count(Deal.id)).where(Deal.is_active == True)
    )).scalar()

    active_banners = (await db.execute(
        select(func.count(Banner.id)).where(Banner.is_active == True)
    )).scalar()

    return {
        "total_users": total_users or 0,
        "total_merchants": total_merchants or 0,
        "total_orders": total_orders or 0,
        "active_drivers": active_drivers or 0,
        "pending_orders": pending_orders or 0,
        "total_revenue": round(total_revenue, 2),
        "pending_merchants": pending_merchants or 0,
        "active_deals": active_deals or 0,
        "active_banners": active_banners or 0,
    }


# ─── Users ────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    base = select(User)
    if role:
        base = base.where(User.role == role)
    if status:
        base = base.where(User.status == status)
    if search:
        q = f"%{search}%"
        base = base.where(or_(User.full_name.ilike(q), User.phone.ilike(q)))

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    stmt = base.order_by(desc(User.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "users": [
            {
                "id": str(u.id),
                "phone": u.phone,
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.post("/users/action")
async def user_action(
    payload: UserAction,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == payload.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.action == "suspend":
        user.status = UserStatus.SUSPENDED
    elif payload.action == "activate":
        user.status = UserStatus.ACTIVE
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await db.commit()
    return {"message": f"User {payload.action}d successfully"}


# ─── Merchants ────────────────────────────────────────────────────────────────

@router.get("/merchants")
async def list_merchants(
    status: Optional[str] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    base = select(Merchant)
    if status:
        base = base.where(Merchant.status == status)
    if category:
        base = base.where(Merchant.category == category)
    if search:
        q = f"%{search}%"
        base = base.where(or_(Merchant.name.ilike(q), Merchant.name_ar.ilike(q), Merchant.city.ilike(q)))

    total_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_stmt)).scalar() or 0

    stmt = base.order_by(desc(Merchant.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    merchants = result.scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "merchants": [
            {
                "id": str(m.id),
                "name": m.name,
                "name_ar": m.name_ar,
                "category": m.category,
                "status": m.status,
                "rating": m.rating,
                "total_orders": m.total_orders,
                "city": m.city,
                "logo_url": m.logo_url,
                "cover_image_url": m.cover_image_url,
                "is_open_now": m.is_open_now,
                "delivery_fee": m.delivery_fee,
                "avg_preparation_time": m.avg_preparation_time,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in merchants
        ],
    }


@router.get("/merchants/{merchant_id}")
async def get_merchant_detail(
    merchant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return {
        "id": str(m.id),
        "name": m.name,
        "name_ar": m.name_ar,
        "description": m.description,
        "description_ar": m.description_ar,
        "category": m.category,
        "status": m.status,
        "logo_url": m.logo_url,
        "cover_image_url": m.cover_image_url,
        "rating": m.rating,
        "total_orders": m.total_orders,
        "total_reviews": m.total_reviews,
        "city": m.city,
        "full_address": m.full_address,
        "phone": m.phone,
        "email": m.email,
        "delivery_fee": m.delivery_fee,
        "min_order_amount": m.min_order_amount,
        "avg_preparation_time": m.avg_preparation_time,
        "is_open_now": m.is_open_now,
        "operating_hours": m.operating_hours,
        "commission_rate": m.commission_rate,
        "latitude": m.latitude,
        "longitude": m.longitude,
    }


@router.put("/merchants/{merchant_id}")
async def update_merchant(
    merchant_id: str,
    payload: MerchantUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        if value is not None:
            setattr(merchant, field, value)

    await db.commit()
    return {"message": "Merchant updated successfully"}


@router.post("/merchants/action")
async def merchant_action(
    payload: MerchantApprove,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Merchant).where(Merchant.id == payload.merchant_id))
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    if payload.action == "approve":
        merchant.status = MerchantStatus.ACTIVE
    elif payload.action == "reject":
        merchant.status = MerchantStatus.INACTIVE
    elif payload.action == "suspend":
        merchant.status = MerchantStatus.SUSPENDED
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await db.commit()
    return {"message": f"Merchant {payload.action}d"}


# ─── Categories ───────────────────────────────────────────────────────────────

@router.get("/merchants/{merchant_id}/categories")
async def list_categories(
    merchant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Category).where(Category.merchant_id == merchant_id).order_by(Category.sort_order)
    )
    cats = result.scalars().all()
    return [{"id": str(c.id), "name": c.name, "name_ar": c.name_ar, "sort_order": c.sort_order, "is_active": c.is_active} for c in cats]


@router.post("/merchants/{merchant_id}/categories")
async def create_category(
    merchant_id: str,
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    cat = Category(
        merchant_id=merchant_id,
        name=payload.name,
        name_ar=payload.name_ar,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return {"id": str(cat.id), "name": cat.name, "name_ar": cat.name_ar}


@router.put("/merchants/{merchant_id}/categories/{cat_id}")
async def update_category(
    merchant_id: str,
    cat_id: str,
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Category).where(Category.id == cat_id, Category.merchant_id == merchant_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(cat, field, value)
    await db.commit()
    return {"message": "Category updated"}


@router.delete("/merchants/{merchant_id}/categories/{cat_id}")
async def delete_category(
    merchant_id: str,
    cat_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Category).where(Category.id == cat_id, Category.merchant_id == merchant_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.delete(cat)
    await db.commit()
    return {"message": "Category deleted"}


# ─── Products ─────────────────────────────────────────────────────────────────

@router.get("/merchants/{merchant_id}/products")
async def list_all_products(
    merchant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Product).where(Product.merchant_id == merchant_id).order_by(Product.sort_order)
    )
    products = result.scalars().all()
    return [_serialize_product_admin(p) for p in products]


@router.post("/merchants/{merchant_id}/products")
async def create_product(
    merchant_id: str,
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    product = Product(
        merchant_id=merchant_id,
        category_id=payload.category_id,
        name=payload.name,
        name_ar=payload.name_ar,
        description=payload.description,
        description_ar=payload.description_ar,
        price=payload.price,
        discounted_price=payload.discounted_price,
        image_url=payload.image_url,
        extra_images=payload.extra_images,
        status=payload.status,
        preparation_time=payload.preparation_time,
        calories=payload.calories,
        tags=payload.tags,
        sort_order=payload.sort_order,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return _serialize_product_admin(product)


@router.put("/merchants/{merchant_id}/products/{product_id}")
async def update_product(
    merchant_id: str,
    product_id: str,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.merchant_id == merchant_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(product, field, value)

    await db.commit()
    return _serialize_product_admin(product)


@router.delete("/merchants/{merchant_id}/products/{product_id}")
async def delete_product(
    merchant_id: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.merchant_id == merchant_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()
    return {"message": "Product deleted"}


def _serialize_product_admin(p: Product) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "name_ar": p.name_ar,
        "description": p.description,
        "description_ar": p.description_ar,
        "price": p.price,
        "discounted_price": p.discounted_price,
        "image_url": p.image_url,
        "extra_images": p.extra_images,
        "status": p.status,
        "preparation_time": p.preparation_time,
        "calories": p.calories,
        "tags": p.tags,
        "sort_order": p.sort_order,
        "total_orders": p.total_orders,
        "rating": p.rating,
        "category_id": str(p.category_id) if p.category_id else None,
    }


# ─── Global products search ───────────────────────────────────────────────────

@router.get("/products")
async def list_all_products_global(
    search: Optional[str] = None,
    merchant_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    base = select(Product).join(Merchant, Product.merchant_id == Merchant.id)
    if merchant_id:
        base = base.where(Product.merchant_id == merchant_id)
    if status:
        base = base.where(Product.status == status)
    if search:
        q = f"%{search}%"
        base = base.where(or_(
            Product.name.ilike(q), Product.name_ar.ilike(q),
            Merchant.name.ilike(q), Merchant.name_ar.ilike(q),
        ))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    stmt = base.order_by(desc(Product.total_orders)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    products = result.scalars().all()

    # Attach merchant names
    merchant_ids = list({str(p.merchant_id) for p in products})
    merchant_names: dict = {}
    if merchant_ids:
        m_result = await db.execute(
            select(Merchant.id, Merchant.name, Merchant.name_ar).where(
                Merchant.id.in_([p.merchant_id for p in products])
            )
        )
        for mid, mname, mname_ar in m_result.fetchall():
            merchant_names[str(mid)] = mname_ar or mname

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "products": [
            {
                **_serialize_product_admin(p),
                "merchant_id": str(p.merchant_id),
                "merchant_name": merchant_names.get(str(p.merchant_id), ""),
            }
            for p in products
        ],
    }


# ─── Orders ───────────────────────────────────────────────────────────────────

@router.get("/orders")
async def list_all_orders(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    base = select(Order)
    if status:
        base = base.where(Order.status == status)
    if search:
        q = f"%{search}%"
        base = base.where(Order.order_number.ilike(q))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    stmt = base.order_by(desc(Order.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    orders = result.scalars().all()

    # Attach customer + merchant names
    customer_ids = [o.customer_id for o in orders]
    merchant_ids_o = [o.merchant_id for o in orders]
    customer_names: dict = {}
    merchant_names_o: dict = {}

    if customer_ids:
        cu_result = await db.execute(
            select(User.id, User.full_name, User.phone).where(User.id.in_(customer_ids))
        )
        for uid, uname, uphone in cu_result.fetchall():
            customer_names[str(uid)] = {"name": uname, "phone": uphone}

    if merchant_ids_o:
        me_result = await db.execute(
            select(Merchant.id, Merchant.name, Merchant.name_ar).where(Merchant.id.in_(merchant_ids_o))
        )
        for mid, mname, mname_ar in me_result.fetchall():
            merchant_names_o[str(mid)] = mname_ar or mname

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "orders": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "status": o.status,
                "total_amount": o.total_amount,
                "is_voice_order": o.is_voice_order,
                "payment_method": o.payment_method,
                "customer_id": str(o.customer_id),
                "customer_name": customer_names.get(str(o.customer_id), {}).get("name", ""),
                "customer_phone": customer_names.get(str(o.customer_id), {}).get("phone", ""),
                "merchant_id": str(o.merchant_id),
                "merchant_name": merchant_names_o.get(str(o.merchant_id), ""),
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
    }


@router.put("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    status: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        order.status = OrderStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    await db.commit()

    # Broadcast to drivers when order becomes ready for pickup
    if status == OrderStatus.READY_FOR_PICKUP:
        from app.api.v1.endpoints.driver import notify_ready_for_pickup
        m_res = await db.execute(select(Merchant).where(Merchant.id == order.merchant_id))
        merchant = m_res.scalar_one_or_none()
        if merchant:
            await notify_ready_for_pickup(order, merchant, db)

    return {"message": "Order status updated", "status": status}


# ─── Deals ────────────────────────────────────────────────────────────────────

@router.get("/deals")
async def list_deals(
    is_active: Optional[bool] = None,
    placement: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(Deal).order_by(Deal.sort_order, desc(Deal.created_at))
    if is_active is not None:
        stmt = stmt.where(Deal.is_active == is_active)
    if placement:
        stmt = stmt.where(Deal.placement == placement)
    result = await db.execute(stmt)
    deals = result.scalars().all()
    return [_serialize_deal(d) for d in deals]


@router.post("/deals")
async def create_deal(
    payload: DealCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    deal = Deal(**{k: v for k, v in payload.model_dump().items() if v is not None})
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return _serialize_deal(deal)


@router.put("/deals/{deal_id}")
async def update_deal(
    deal_id: str,
    payload: DealUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(deal, field, value)
    await db.commit()
    return _serialize_deal(deal)


@router.delete("/deals/{deal_id}")
async def delete_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    await db.delete(deal)
    await db.commit()
    return {"message": "Deal deleted"}


def _serialize_deal(d: Deal) -> dict:
    return {
        "id": str(d.id),
        "title": d.title,
        "title_ar": d.title_ar,
        "description": d.description,
        "image_url": d.image_url,
        "original_price": d.original_price,
        "discounted_price": d.discounted_price,
        "discount_pct": d.discount_pct,
        "valid_from": d.valid_from.isoformat() if d.valid_from else None,
        "valid_until": d.valid_until.isoformat() if d.valid_until else None,
        "is_active": d.is_active,
        "placement": d.placement,
        "merchant_id": str(d.merchant_id) if d.merchant_id else None,
        "sort_order": d.sort_order,
        "extra_images": d.extra_images,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


# ─── Banners ──────────────────────────────────────────────────────────────────

@router.get("/banners")
async def list_banners(
    is_active: Optional[bool] = None,
    placement: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(Banner).order_by(Banner.sort_order, desc(Banner.created_at))
    if is_active is not None:
        stmt = stmt.where(Banner.is_active == is_active)
    if placement:
        stmt = stmt.where(Banner.placement == placement)
    result = await db.execute(stmt)
    banners = result.scalars().all()
    return [_serialize_banner(b) for b in banners]


@router.post("/banners")
async def create_banner(
    payload: BannerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    banner = Banner(**{k: v for k, v in payload.model_dump().items() if v is not None})
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return _serialize_banner(banner)


@router.put("/banners/{banner_id}")
async def update_banner(
    banner_id: str,
    payload: BannerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(banner, field, value)
    await db.commit()
    return _serialize_banner(banner)


@router.delete("/banners/{banner_id}")
async def delete_banner(
    banner_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    await db.delete(banner)
    await db.commit()
    return {"message": "Banner deleted"}


def _serialize_banner(b: Banner) -> dict:
    return {
        "id": str(b.id),
        "title": b.title,
        "title_ar": b.title_ar,
        "subtitle_ar": b.subtitle_ar,
        "image_url": b.image_url,
        "link_url": b.link_url,
        "placement": b.placement,
        "merchant_id": str(b.merchant_id) if b.merchant_id else None,
        "valid_from": b.valid_from.isoformat() if b.valid_from else None,
        "valid_until": b.valid_until.isoformat() if b.valid_until else None,
        "is_active": b.is_active,
        "sort_order": b.sort_order,
        "bg_color": b.bg_color,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }
