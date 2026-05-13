from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.core.database import get_db
from app.models.deals import Deal, Banner

router = APIRouter(prefix="/deals", tags=["deals"])


def _deal_dict(d: Deal) -> dict:
    now = datetime.now(timezone.utc)
    countdown_seconds = 0
    if d.valid_until:
        delta = d.valid_until - now
        countdown_seconds = max(0, int(delta.total_seconds()))

    return {
        "id": str(d.id),
        "title": d.title_ar or d.title,
        "title_en": d.title,
        "description": d.description,
        "image_url": d.image_url,
        "original_price": d.original_price,
        "discounted_price": d.discounted_price,
        "discount_pct": d.discount_pct,
        "placement": d.placement,
        "sort_order": d.sort_order,
        "countdown_seconds": countdown_seconds,
        "valid_until": d.valid_until.isoformat() if d.valid_until else None,
        "merchant_id": str(d.merchant_id) if d.merchant_id else None,
        "product_id": str(d.product_id) if d.product_id else None,
        "extra_images": d.extra_images,
    }


def _banner_dict(b: Banner) -> dict:
    return {
        "id": str(b.id),
        "title": b.title_ar or b.title,
        "subtitle": b.subtitle_ar,
        "image_url": b.image_url,
        "link_url": b.link_url,
        "placement": b.placement,
        "sort_order": b.sort_order,
        "bg_color": b.bg_color,
        "merchant_id": str(b.merchant_id) if b.merchant_id else None,
    }


@router.get("")
async def list_deals(
    placement: str | None = Query(None, description="Filter: home, featured, merchant"),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    conds = [
        Deal.is_active == True,  # noqa: E712
        or_(Deal.valid_until == None, Deal.valid_until >= now),  # noqa: E711
        or_(Deal.valid_from == None, Deal.valid_from <= now),  # noqa: E711
    ]
    if placement:
        conds.append(Deal.placement == placement)

    result = await db.execute(
        select(Deal).where(and_(*conds)).order_by(Deal.sort_order, Deal.id).limit(limit)
    )
    deals = result.scalars().all()
    return {"deals": [_deal_dict(d) for d in deals], "total": len(deals)}


@router.get("/banners")
async def list_banners(
    placement: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    conds = [
        Banner.is_active == True,  # noqa: E712
        or_(Banner.valid_until == None, Banner.valid_until >= now),  # noqa: E711
        or_(Banner.valid_from == None, Banner.valid_from <= now),  # noqa: E711
    ]
    if placement:
        conds.append(Banner.placement == placement)

    result = await db.execute(
        select(Banner).where(and_(*conds)).order_by(Banner.sort_order, Banner.id)
    )
    banners = result.scalars().all()
    return {"banners": [_banner_dict(b) for b in banners]}
