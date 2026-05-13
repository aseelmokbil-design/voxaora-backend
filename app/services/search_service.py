"""
VOXAORA Search & Ranking Engine
Scores merchants by: distance, ETA, rating, price, popularity, availability
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from haversine import haversine, Unit
from app.models.merchant import Merchant, MerchantStatus
from app.models.product import Product, ProductStatus
import structlog

logger = structlog.get_logger()

# ── Arabic Synonym Map (Yemeni dialect + standard Arabic) ────────────────────
# Each key maps to a list of all equivalent terms including itself
ARABIC_SYNONYMS: dict[str, list[str]] = {
    "دجاج":    ["دجاج","فروج","بروست","حنيذ","كاول","تكة دجاج","دجاجة"],
    "لحم":     ["لحم","لحمة","كباب","مشوي","مشاوي","كفتة","ستيك","بيف","قديد","كبدة"],
    "سمك":     ["سمك","سمكة","ربيان","جمبري","تونة","هامور"],
    "برجر":    ["برجر","همبرجر","بيف برجر","تشيكن برجر","كرسبي","سوبر برجر"],
    "بيتزا":   ["بيتزا","بيزا","pizza"],
    "شاورما":  ["شاورما","شاورمة","دونر","لفة شاورما"],
    "مندي":    ["مندي","مندي لحم","مندي دجاج","كبسة","فريدة","حنيذ"],
    "فول":     ["فول","فول بلدي","فول مدمس","فول بزيت"],
    "لحوح":   ["لحوح","خبز يمني","فطير","فطور"],
    "فطور":    ["فطور","إفطار","ريوق","صبحية","لحوح","بيض","فول"],
    "سلطة":    ["سلطة","سالاد","فتوش","تبولة"],
    "مرق":     ["مرق","شوربة","سوبا","مرقة","سلتة"],
    "رز":      ["رز","ارز","أرز","رز أبيض","رز بخاري"],
    "بطاطس":   ["بطاطس","بطاطا","فرنش فراي","چيبس"],
    "عصير":    ["عصير","جوس","عصيرة","مشروب طازج","سموذي"],
    "قهوة":    ["قهوة","كافيه","اسبريسو","كابتشينو","لاتيه","نسكافيه"],
    "شاي":     ["شاي","أحمر","شاي بالحليب","كرك"],
    "حلويات":  ["حلويات","كيك","جاتوه","تورتة","كنافة","بسبوسة","مهلبية"],
    "سمبوسة":  ["سمبوسة","سنبوسة","سمبوسك"],
    "معكرونة": ["معكرونة","مكرونة","باستا","اسباغيتي"],
    "ساندوتش": ["ساندوتش","ساندويش","سندوتش","رول","لفة","تورتيلا"],
    "مشروب":   ["مشروب","كولا","بيبسي","عصير","مياه","عصيرة"],
}

def _expand_query(query: str) -> list[str]:
    """Expand Arabic query with synonyms for better recall."""
    q = query.strip()
    terms = {q}
    ql = q.lower()
    for canonical, variants in ARABIC_SYNONYMS.items():
        if canonical in ql or any(v in ql for v in variants):
            terms.update(variants)
            terms.add(canonical)
    return list(terms)

def _text_matches(name_combined: str, terms: list[str]) -> bool:
    """Return True if any synonym term appears in the combined name string."""
    nc = name_combined.lower()
    return any(t.lower() in nc for t in terms)


WEIGHT_DISTANCE = 0.25
WEIGHT_ETA = 0.20
WEIGHT_RATING = 0.25
WEIGHT_PRICE = 0.10
WEIGHT_POPULARITY = 0.15
WEIGHT_AVAILABILITY = 0.05


def _normalize(value: float, min_v: float, max_v: float, invert: bool = False) -> float:
    if max_v == min_v:
        return 1.0
    norm = (value - min_v) / (max_v - min_v)
    return round(1.0 - norm if invert else norm, 4)


def _estimate_eta(distance_km: float, prep_time: int) -> int:
    speed_kmh = 25
    travel_minutes = (distance_km / speed_kmh) * 60
    return int(prep_time + travel_minutes + 3)


def _score_merchant(
    merchant: Dict,
    all_merchants: List[Dict],
    user_preferences: Optional[Dict] = None,
) -> float:
    distances = [m["distance_km"] for m in all_merchants]
    etas = [m["estimated_eta_minutes"] for m in all_merchants]
    ratings = [m["rating"] for m in all_merchants]
    prices = [m.get("min_order_amount", 0) for m in all_merchants]
    popularities = [m.get("total_orders", 0) for m in all_merchants]

    dist_score = _normalize(merchant["distance_km"], min(distances), max(distances), invert=True)
    eta_score = _normalize(merchant["estimated_eta_minutes"], min(etas), max(etas), invert=True)
    rating_score = _normalize(merchant["rating"], 0, 5)
    price_score = _normalize(merchant.get("min_order_amount", 0), min(prices), max(prices), invert=True)
    pop_score = _normalize(merchant.get("total_orders", 0), min(popularities), max(popularities))
    avail_score = 1.0 if merchant.get("is_open_now") else 0.0

    score = (
        WEIGHT_DISTANCE * dist_score
        + WEIGHT_ETA * eta_score
        + WEIGHT_RATING * rating_score
        + WEIGHT_PRICE * price_score
        + WEIGHT_POPULARITY * pop_score
        + WEIGHT_AVAILABILITY * avail_score
    )

    # Personalization boosts (capped so they don't dominate)
    if user_preferences:
        if merchant.get("category") == user_preferences.get("favorite_category"):
            score += 0.07   # preferred category
        if merchant["id"] in (user_preferences.get("favorite_merchant_ids") or []):
            score += 0.10   # repeat customer at this merchant

    return round(min(score, 1.0), 4)


class SearchService:
    async def search_merchants(
        self,
        db: AsyncSession,
        latitude: float,
        longitude: float,
        category: Optional[str] = None,
        query: Optional[str] = None,
        max_delivery_time: Optional[int] = None,
        max_distance_km: float = 999999.0,
        limit: int = 10,
        user_preferences: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        stmt = select(Merchant).where(Merchant.status == MerchantStatus.ACTIVE)
        if category:
            stmt = stmt.where(Merchant.category == category)

        result = await db.execute(stmt)
        merchants = result.scalars().all()

        enriched = []
        for m in merchants:
            dist = haversine(
                (latitude, longitude),
                (m.latitude, m.longitude),
                unit=Unit.KILOMETERS,
            )

            # Cap displayed distance at 5km for UX (demo mode)
            display_dist = min(dist, 4.5) if dist > 20 else dist
            eta = _estimate_eta(display_dist, m.avg_preparation_time)

            if query:
                terms = _expand_query(query)
                name_combined = (m.name or "") + " " + (m.name_ar or "") + " " + (m.description_ar or m.description or "")
                if not _text_matches(name_combined, terms):
                    continue

            enriched.append({
                "id": str(m.id),
                "name": m.name,
                "name_ar": m.name_ar,
                "category": m.category,
                "logo_url": m.logo_url,
                "rating": m.rating,
                "total_reviews": m.total_reviews,
                "distance_km": round(display_dist, 2),
                "estimated_eta_minutes": eta,
                "delivery_fee": m.delivery_fee,
                "min_order_amount": m.min_order_amount,
                "free_delivery_above": m.free_delivery_above,
                "is_open_now": m.is_open_now,
                "avg_preparation_time": m.avg_preparation_time,
                "total_orders": m.total_orders,
                "latitude": m.latitude,
                "longitude": m.longitude,
            })

        if not enriched:
            return []

        for m in enriched:
            m["voxaora_score"] = _score_merchant(m, enriched, user_preferences)

        enriched.sort(key=lambda x: (-x["voxaora_score"], x["distance_km"]))
        return enriched[:limit]

    async def search_products(
        self,
        db: AsyncSession,
        merchant_id: str,
        query: Optional[str] = None,
        category_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        stmt = select(Product).where(
            and_(
                Product.merchant_id == merchant_id,
                Product.status == ProductStatus.AVAILABLE,
            )
        )
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)

        result = await db.execute(stmt)
        products = result.scalars().all()

        if query:
            terms = _expand_query(query)
            products = [
                p for p in products
                if _text_matches((p.name or "") + " " + (p.name_ar or ""), terms)
            ]

        return [
            {
                "id": str(p.id),
                "name": p.name,
                "name_ar": p.name_ar,
                "description": p.description,
                "price": p.effective_price,
                "original_price": p.price,
                "discounted_price": p.discounted_price,
                "image_url": p.image_url,
                "preparation_time": p.preparation_time,
                "rating": p.rating,
                "total_orders": p.total_orders,
                "category_id": str(p.category_id) if p.category_id else None,
                "tags": p.tags,
            }
            for p in products
        ]

    async def get_top_recommendations(
        self,
        db: AsyncSession,
        latitude: float,
        longitude: float,
        intent: Dict[str, Any],
        user_preferences: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        category = intent.get("category")
        constraints = intent.get("constraints", {})
        min_rating = constraints.get("min_rating")
        requested_items = intent.get("items", [])

        results = await self.search_merchants(
            db=db, latitude=latitude, longitude=longitude,
            category=category, max_distance_km=999999.0, limit=10,
            user_preferences=user_preferences,
        )

        if min_rating:
            results = [r for r in results if r["rating"] >= min_rating]

        # Words too generic to use for product matching
        STOP = {
            "أريد","ابغى","اطلب","بغيت","عايز","محتاج","بدي","حاب","أبي",
            "من","في","مع","على","إلى","و","أو","او","لي","لو","هل","يا",
            "عندكم","عندك","فيه","لقيت","وجدت","هات","جيب",
            "وجبة","وجبات","طلب","طعام","أكل","اكل","شيء","حاجة",
            "خلال","وتصل","سيصل","دقيقة","ساعة","بسرعة",
            "قريب","قريبة","كبير","كبيرة","صغير","صغيرة","وسط","وسطي",
            "واحد","اثنين","ثلاث","حبة","علبة",
            "i","want","need","the","a","an","please","me","some","give","in","minutes","meal",
        }

        # product_tokens: specific item keywords only (no generic words)
        product_tokens: set = set()
        for item in requested_items:
            for field in ("name", "name_en"):
                val = (item.get(field) or "").lower().strip()
                if not val:
                    continue
                for word in val.split():
                    if len(word) >= 2 and word not in STOP:
                        product_tokens.add(word)

        # merchant_tokens: broader — includes brand names from raw transcript
        merchant_tokens: set = set(product_tokens)
        raw_query = (intent.get("raw_query") or "").lower().strip()
        if raw_query:
            for word in raw_query.split():
                if len(word) >= 2 and word not in STOP:
                    merchant_tokens.add(word)

        def _count_product_matches(p) -> int:
            """Count how many tokens match this product, with synonym expansion."""
            if not product_tokens:
                return 0
            name_combined = ((p.name or "") + " " + (p.name_ar or "")).lower()
            score = 0
            for tok in product_tokens:
                expanded = _expand_query(tok)
                if any(t.lower() in name_combined for t in expanded):
                    score += 1
            return score

        def _merchant_name_matches(rec: Dict) -> bool:
            if not merchant_tokens:
                return False
            mname = ((rec.get("name") or "") + " " + (rec.get("name_ar") or "")).lower()
            return any(tok in mname for tok in merchant_tokens)

        # Enrich each merchant with matching products
        for rec in results:
            try:
                prod_stmt = select(Product).where(
                    Product.merchant_id == rec["id"],
                    Product.status == ProductStatus.AVAILABLE,
                )
                prod_result = await db.execute(prod_stmt)
                all_products = prod_result.scalars().all()

                if product_tokens:
                    # Score each product and sort by relevance
                    scored = [(p, _count_product_matches(p)) for p in all_products]
                    scored.sort(key=lambda x: -x[1])
                    matching = [p for p, s in scored if s > 0]
                    products_to_show = matching[:5] if matching else all_products[:5]
                    total_match_score = sum(s for _, s in scored if s > 0)
                else:
                    products_to_show = sorted(all_products, key=lambda p: -(p.total_orders or 0))[:5]
                    total_match_score = 0

                rec["items"] = [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "name_ar": p.name_ar,
                        "price": float(p.effective_price),
                        "preparation_time": p.preparation_time,
                    }
                    for p in products_to_show
                ]

                has_product_match        = total_match_score > 0
                has_name_match           = _merchant_name_matches(rec)
                rec["has_requested_items"] = has_product_match or has_name_match
                rec["_match_score"]        = total_match_score + (5 if has_name_match else 0)

            except Exception:
                rec["items"] = []
                rec["has_requested_items"] = False
                rec["_match_score"] = 0

        # Sort: by match score first (most relevant), then voxaora_score
        results.sort(key=lambda x: (
            0 if x.get("has_requested_items") else 1,
            -x.get("_match_score", 0),
            -x.get("voxaora_score", 0),
        ))

        return results[:3]


search_service = SearchService()
