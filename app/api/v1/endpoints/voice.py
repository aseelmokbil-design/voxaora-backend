import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.voice_session import VoiceSession
from app.models.order import Order, OrderStatus
from app.models.merchant import Merchant
from app.services.voice_service import voice_service
from app.services.search_service import search_service
from app.schemas.voice import (
    VoiceIntentRequest, VoiceIntentResponse,
    VoiceConfirmRequest, VoiceConfirmResponse,
    VoiceContext,
)
from app.services.order_service import order_service
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/greeting")
async def get_greeting(language: str = "ar"):
    return {"greeting": voice_service.get_greeting(language), "language": language}


async def _save_session(
    db: AsyncSession, user: User, transcript: str, intent: dict,
    lat: float, lng: float, recommendations: list, tts_text: str, ms: int,
) -> str:
    """Save voice session, return session_id string."""
    try:
        session = VoiceSession(
            user_id=user.id,
            transcript=transcript,
            transcript_language=intent.get("language", "ar"),
            transcript_confidence=float(intent.get("confidence", 0.9)),
            raw_intent=intent,
            intent_category=intent.get("category"),
            intent_items=intent.get("items", []),
            intent_constraints=intent.get("constraints", {}),
            user_latitude=lat,
            user_longitude=lng,
            search_results=recommendations,
            tts_response=tts_text,
            processing_time_ms=ms,
            was_successful=len(recommendations) > 0,
        )
        db.add(session)
        await db.flush()
        return str(session.id)
    except Exception as e:
        logger.error("voice_session_save_failed", error=str(e))
        import uuid
        return str(uuid.uuid4())   # fallback — no session stored but flow continues


async def _get_user_prefs_lightweight(db: AsyncSession, user_id) -> dict:
    """Quick preference lookup — top category + favorite merchants from last 20 orders."""
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == user_id, Order.status == OrderStatus.DELIVERED)
        .order_by(desc(Order.created_at))
        .limit(20)
    )
    orders = result.scalars().all()
    category_count: dict = {}
    merchant_count: dict = {}
    for o in orders:
        mr = await db.execute(select(Merchant).where(Merchant.id == o.merchant_id))
        m = mr.scalar_one_or_none()
        if m:
            category_count[m.category] = category_count.get(m.category, 0) + 1
            mid = str(o.merchant_id)
            merchant_count[mid] = merchant_count.get(mid, 0) + 1
    return {
        "favorite_category": max(category_count, key=category_count.get) if category_count else None,
        "favorite_merchant_ids": sorted(merchant_count, key=merchant_count.get, reverse=True)[:3],
    }


async def _handle_voice_reorder(
    db: AsyncSession, user: User, lat: float, lng: float, intent: dict, start: float,
) -> VoiceIntentResponse | None:
    """If the user said 'reorder', clone last order and return a done response."""
    result = await db.execute(
        select(Order)
        .where(Order.customer_id == user.id, Order.status == OrderStatus.DELIVERED)
        .order_by(desc(Order.created_at))
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if not last:
        return None

    mr = await db.execute(select(Merchant).where(Merchant.id == last.merchant_id))
    merchant = mr.scalar_one_or_none()
    if not merchant or merchant.status != "active":
        return None

    try:
        items_data = []
        for item in (last.items or []):
            from app.models.product import Product, ProductStatus
            pr = await db.execute(
                select(Product).where(Product.id == item.product_id, Product.status == ProductStatus.AVAILABLE)
            )
            product = pr.scalar_one_or_none()
            if product:
                items_data.append({"product_id": str(item.product_id), "quantity": item.quantity})

        if not items_data:
            return None

        new_order = await order_service.create_order(
            db=db, customer=user, merchant_id=str(merchant.id),
            items_data=items_data, payment_method="cash", is_voice_order=True,
        )

        mname = merchant.name_ar or merchant.name
        tts = f"تمام! أعدت طلبك من {mname}. سيصلك خلال {new_order.estimated_delivery_time} دقيقة إن شاء الله."
        ms = int((time.time() - start) * 1000)

        return VoiceIntentResponse(
            session_id=str(new_order.id),
            transcript="",
            intent={**intent, "action": "reorder", "order_id": str(new_order.id)},
            recommendations=[],
            tts_response=tts,
            tts_audio_url=None,
            processing_ms=ms,
        )
    except Exception as e:
        logger.warning("voice_reorder_failed", error=str(e))
        return None


async def _process_voice(
    db: AsyncSession, user: User, transcript: str,
    lat: float, lng: float, start: float,
    context: VoiceContext | None = None,
) -> VoiceIntentResponse:
    # Multi-turn: if context provided, try follow-up intent first
    if context and context.previous_results:
        prev_results = [r.model_dump() for r in context.previous_results]
        intent = await voice_service.extract_followup_intent(
            transcript=transcript,
            previous_transcript=context.previous_transcript,
            previous_results=prev_results,
        )
    else:
        intent = await voice_service.extract_intent(transcript, user.preferred_language or "ar")

    lang = intent.get("language", "ar")

    # If follow-up resolved to a direct selection, return it — client auto-confirms
    if intent.get("action") == "select":
        index = int(intent.get("index", 0))
        tts = voice_service.build_selection_response(index, lang)
        ms = int((time.time() - start) * 1000)
        prev_sid = context.previous_session_id if context else ""
        return VoiceIntentResponse(
            session_id=prev_sid,
            transcript=transcript,
            intent={**intent, "selected_index": index},
            recommendations=[],
            tts_response=tts,
            tts_audio_url=None,
            processing_ms=ms,
        )

    # Handle voice reorder ("أعد الطلب السابق")
    if intent.get("is_reorder"):
        reorder_response = await _handle_voice_reorder(db, user, lat, lng, intent, start)
        if reorder_response:
            return reorder_response
        # If reorder failed, fall through to fresh search

    # Fetch personalization preferences (non-blocking — never breaks search)
    user_prefs = None
    try:
        user_prefs = await _get_user_prefs_lightweight(db, user.id)
    except Exception:
        pass

    recommendations = await search_service.get_top_recommendations(
        db=db, latitude=lat, longitude=lng, intent=intent, user_preferences=user_prefs,
    )

    # Build natural language response
    if not recommendations:
        items = intent.get("items", [])
        item_name = items[0].get("name", "") if items else ""
        tts_text = voice_service.build_no_results_response(item_name, lang)
    else:
        tts_text = voice_service.build_results_response(recommendations, lang, intent)

    ms = int((time.time() - start) * 1000)
    session_id = await _save_session(
        db, user, transcript, intent, lat, lng, recommendations, tts_text, ms,
    )

    return VoiceIntentResponse(
        session_id=session_id,
        transcript=transcript,
        intent=intent,
        recommendations=recommendations,
        tts_response=tts_text,
        tts_audio_url=None,
        processing_ms=ms,
    )


@router.post("/transcribe", response_model=VoiceIntentResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    latitude: float = Form(24.7136),
    longitude: float = Form(46.6753),
    context_json: str = Form(""),       # optional JSON-encoded VoiceContext
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start = time.time()
    try:
        content = await audio.read()
        import io, json as _json
        transcription = await voice_service.transcribe_audio(
            io.BytesIO(content), audio.filename or "audio.webm"
        )
        transcript = (transcription.get("text") or "").strip()

        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="لم أتمكن من فهم الكلام. تحدث بوضوح أقرب للميكروفون وحاول مجدداً."
            )

        context = None
        if context_json:
            try:
                context = VoiceContext(**_json.loads(context_json))
            except Exception:
                pass

        return await _process_voice(db, current_user, transcript, latitude, longitude, start, context)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("transcribe_failed", error=str(e), user=str(current_user.id))
        raise HTTPException(status_code=500, detail=f"فشل معالجة الصوت: {str(e)}")


@router.post("/intent", response_model=VoiceIntentResponse)
async def process_intent(
    payload: VoiceIntentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start = time.time()
    try:
        return await _process_voice(
            db, current_user, payload.transcript,
            payload.latitude, payload.longitude, start,
            payload.context,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("intent_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"فشل معالجة الطلب: {str(e)}")


@router.post("/confirm", response_model=VoiceConfirmResponse)
async def confirm_voice_order(
    payload: VoiceConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(
            select(VoiceSession).where(
                VoiceSession.id == payload.session_id,
                VoiceSession.user_id == current_user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="جلسة الصوت غير موجودة")

        results = session.search_results or []
        if not results or payload.selected_index >= len(results):
            raise HTTPException(status_code=400, detail="اختيار غير صحيح")

        selected = results[payload.selected_index]
        session.selected_merchant_id = selected["id"]

        items = session.intent_items or []
        if not items:
            # Fallback: create a generic order with first available product
            items = [{"name": "طلب صوتي", "name_en": "voice order", "quantity": 1}]

        order = await order_service.create_voice_order(
            db=db,
            customer=current_user,
            merchant_id=selected["id"],
            items=items,
            voice_session_id=str(session.id),
            payment_method=payload.payment_method,
            address_id=payload.address_id,
        )

        lang = session.transcript_language or current_user.preferred_language or "ar"
        merchant_name = selected.get("name_ar" if lang == "ar" else "name", selected.get("name", ""))
        eta = selected.get("estimated_eta_minutes", 25)

        tts = voice_service.build_confirmation_response(
            merchant_name=merchant_name, eta=eta, language=lang,
            order_number=order.order_number,
        )

        return VoiceConfirmResponse(
            order_id=str(order.id),
            order_number=order.order_number,
            merchant_name=selected.get("name", ""),
            estimated_eta=eta,
            total_amount=float(order.total_amount),
            tts_response=tts,
            status=str(order.status),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("confirm_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"فشل تأكيد الطلب: {str(e)}")
