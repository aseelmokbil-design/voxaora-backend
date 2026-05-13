from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from app.core.database import get_db
from app.api.v1.deps import get_current_user, require_admin
from app.models.user import User, UserRole
from app.models.merchant import Merchant, MerchantStatus
from app.models.product import Product, Category, ProductStatus
from app.services.search_service import search_service

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.get("/search")
async def search_merchants(
    latitude: float = Query(...),
    longitude: float = Query(...),
    category: Optional[str] = None,
    query: Optional[str] = None,
    max_delivery_time: Optional[int] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    results = await search_service.search_merchants(
        db=db,
        latitude=latitude,
        longitude=longitude,
        category=category,
        query=query,
        max_delivery_time=max_delivery_time,
        limit=limit,
    )
    return {"merchants": results, "total": len(results)}


@router.get("/{merchant_id}")
async def get_merchant(merchant_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    merchant = result.scalar_one_or_none()
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return {
        "id": str(merchant.id),
        "name": merchant.name,
        "name_ar": merchant.name_ar,
        "description": merchant.description,
        "description_ar": merchant.description_ar,
        "category": merchant.category,
        "logo_url": merchant.logo_url,
        "cover_image_url": merchant.cover_image_url,
        "rating": merchant.rating,
        "total_reviews": merchant.total_reviews,
        "delivery_fee": merchant.delivery_fee,
        "min_order_amount": merchant.min_order_amount,
        "free_delivery_above": merchant.free_delivery_above,
        "avg_preparation_time": merchant.avg_preparation_time,
        "is_open_now": merchant.is_open_now,
        "operating_hours": merchant.operating_hours,
        "phone": merchant.phone,
        "full_address": merchant.full_address,
        "city": merchant.city,
    }


@router.get("/{merchant_id}/menu")
async def get_merchant_menu(merchant_id: str, db: AsyncSession = Depends(get_db)):
    cat_result = await db.execute(
        select(Category).where(Category.merchant_id == merchant_id, Category.is_active == True)
        .order_by(Category.sort_order)
    )
    categories = cat_result.scalars().all()

    prod_result = await db.execute(
        select(Product).where(
            Product.merchant_id == merchant_id,
            Product.status == ProductStatus.AVAILABLE,
        ).order_by(Product.sort_order)
    )
    products = prod_result.scalars().all()

    products_by_cat: dict = {}
    uncategorized = []
    for p in products:
        cat_id = str(p.category_id) if p.category_id else None
        if cat_id:
            products_by_cat.setdefault(cat_id, []).append(_serialize_product(p))
        else:
            uncategorized.append(_serialize_product(p))

    menu = []
    for cat in categories:
        menu.append({
            "id": str(cat.id),
            "name": cat.name,
            "name_ar": cat.name_ar,
            "products": products_by_cat.get(str(cat.id), []),
        })
    if uncategorized:
        menu.append({"id": None, "name": "Other", "name_ar": "أخرى", "products": uncategorized})

    return {"categories": menu}


def _serialize_product(p: Product) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "name_ar": p.name_ar,
        "description": p.description,
        "description_ar": p.description_ar,
        "price": p.effective_price,
        "original_price": p.price,
        "image_url": p.image_url,
        "preparation_time": p.preparation_time,
        "rating": p.rating,
        "tags": p.tags,
        "options": p.options,
    }


@router.get("/{merchant_id}/products/{product_id}")
async def get_product(merchant_id: str, product_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.merchant_id == merchant_id,
            Product.status == ProductStatus.AVAILABLE,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    related_result = await db.execute(
        select(Product).where(
            Product.merchant_id == merchant_id,
            Product.id != product.id,
            Product.status == ProductStatus.AVAILABLE,
        ).order_by(desc(Product.total_orders)).limit(6)
    )
    related = related_result.scalars().all()

    return {
        **_serialize_product(product),
        "calories": product.calories,
        "total_orders": product.total_orders,
        "related": [_serialize_product(r) for r in related],
    }


@router.get("/{merchant_id}/products")
async def list_products(
    merchant_id: str,
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    results = await search_service.search_products(db, merchant_id, query=q)
    return {"products": results}
