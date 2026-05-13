import json
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import os, uuid, shutil

from app.core.database import get_db, AsyncSessionLocal
from app.core.security import decode_token
from app.api.v1.deps import require_driver
from app.api.v1.ws_manager import driver_ws
from app.models.user import User
from app.models.driver import Driver
from app.models.order import Order, OrderStatus
from app.models.merchant import Merchant
from app.models.driver_extras import DriverDocument, DriverTransaction

router = APIRouter(prefix="/driver", tags=["driver"])

UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

# ── Incentive tiers ───────────────────────────────────────────────────────────
DAILY_TARGETS = [
    {"target": 15, "bonus": 3000, "label": "نجم الذهب"},
    {"target": 10, "bonus": 1500, "label": "نجم الفضة"},
    {"target": 5,  "bonus": 500,  "label": "نجم البرونز"},
]
RATING_BONUSES = [
    {"min_rating": 4.8, "pct": 0.10, "label": "سائق ممتاز"},
    {"min_rating": 4.5, "pct": 0.05, "label": "سائق مميز"},
]
PEAK_HOURS = [(12, 14), (19, 22)]  # (start_hour, end_hour) UTC+3


# ── Pydantic ──────────────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: str  # available | offline

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float

class StepUpdate(BaseModel):
    step: str  # at_store | picked_up | delivered

class WithdrawalRequest(BaseModel):
    amount: float
    notes: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_driver(db: AsyncSession, user_id: str) -> Driver:
    result = await db.execute(select(Driver).where(Driver.user_id == user_id))
    driver = result.scalar_one_or_none()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver profile not found")
    return driver


def _is_peak_hour() -> bool:
    hour = (datetime.utcnow().hour + 3) % 24  # UTC+3
    return any(s <= hour < e for s, e in PEAK_HOURS)


def _driver_earnings(delivery_fee: float, rating: float) -> float:
    base = delivery_fee * 0.8
    if _is_peak_hour():
        base *= 1.2
    for rb in RATING_BONUSES:
        if rating >= rb["min_rating"]:
            base *= (1 + rb["pct"])
            break
    return round(base, 2)


async def _record_tx(db: AsyncSession, driver_id, tx_type: str, amount: float,
                     desc: str, ref: str = None, status: str = "completed"):
    tx = DriverTransaction(
        driver_id=driver_id, tx_type=tx_type, amount=amount,
        description=desc, status=status, reference_id=ref,
    )
    db.add(tx)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def driver_ws_endpoint(
    websocket: WebSocket,
    token: str = "",
):
    # Authenticate
    user_id: Optional[str] = None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("no sub")
    except Exception:
        await websocket.accept()
        await websocket.send_json({"type": "error", "detail": "unauthorized"})
        await websocket.close(code=4001)
        return

    async with AsyncSessionLocal() as db:
        # Verify driver exists
        driver_result = await db.execute(select(Driver).where(Driver.user_id == user_id))
        driver = driver_result.scalar_one_or_none()
        if not driver:
            await websocket.accept()
            await websocket.send_json({"type": "error", "detail": "not_a_driver"})
            await websocket.close(code=4003)
            return

        driver_id = str(driver.id)

    await driver_ws.connect(driver_id, websocket)
    await websocket.send_json({"type": "connected", "driver_id": driver_id})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            if msg.get("type") == "location":
                lat = msg.get("lat")
                lng = msg.get("lng")
                if lat is not None and lng is not None:
                    async with AsyncSessionLocal() as db:
                        d_res = await db.execute(select(Driver).where(Driver.id == driver_id))
                        drv = d_res.scalar_one_or_none()
                        if drv:
                            drv.current_latitude = lat
                            drv.current_longitude = lng
                            await db.commit()

            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        driver_ws.disconnect(driver_id)


# ── Helper used by admin to broadcast ────────────────────────────────────────

async def notify_ready_for_pickup(order: Order, merchant: Merchant, db: AsyncSession):
    """Called by admin when order status → ready_for_pickup."""
    result = await db.execute(
        select(Driver.id).where(Driver.status == "available")
    )
    available_ids = {str(row[0]) for row in result.fetchall()}
    if not available_ids:
        return

    order_payload = {
        "id": str(order.id),
        "order_number": order.order_number,
        "merchant_name": merchant.name_ar or merchant.name,
        "merchant_address": merchant.full_address or merchant.city or "",
        "merchant_lat": merchant.latitude,
        "merchant_lng": merchant.longitude,
        "delivery_address": order.delivery_address,
        "total_amount": order.total_amount,
        "delivery_fee": order.delivery_fee,
        "driver_earnings": order.delivery_fee * 0.8,
        "items_count": len(order.items) if order.items else 0,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
    await driver_ws.broadcast_new_order(order_payload, available_ids)


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/me")
async def get_driver_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    return {
        "id": str(driver.id),
        "user_id": str(driver.user_id),
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "vehicle_type": driver.vehicle_type,
        "vehicle_plate": driver.vehicle_plate,
        "vehicle_model": driver.vehicle_model,
        "status": driver.status,
        "rating": driver.rating,
        "total_deliveries": driver.total_deliveries,
        "total_earnings": driver.total_earnings,
        "city": driver.city,
        "is_verified": driver.is_verified,
    }


@router.put("/status")
async def update_status(
    payload: StatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    if payload.status not in {"available", "offline"}:
        raise HTTPException(status_code=400, detail="Status must be available or offline")
    if driver.status == "busy" and payload.status == "offline":
        raise HTTPException(status_code=400, detail="لا يمكن الخروج أثناء وجود طلب نشط")
    driver.status = payload.status
    await db.commit()
    return {"status": driver.status}


@router.put("/location")
async def update_location(
    payload: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    driver.current_latitude = payload.latitude
    driver.current_longitude = payload.longitude
    await db.commit()
    return {"ok": True}


# ── Orders ────────────────────────────────────────────────────────────────────

@router.get("/orders/available")
async def get_available_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    if driver.status != "available":
        return {"orders": []}

    stmt = (
        select(Order, Merchant)
        .join(Merchant, Order.merchant_id == Merchant.id)
        .where(and_(Order.status == OrderStatus.READY_FOR_PICKUP, Order.driver_id.is_(None)))
        .order_by(desc(Order.created_at))
        .limit(20)
    )
    result = await db.execute(stmt)

    return {
        "orders": [
            {
                "id": str(order.id),
                "order_number": order.order_number,
                "merchant_name": merchant.name_ar or merchant.name,
                "merchant_address": merchant.full_address or merchant.city or "",
                "merchant_lat": merchant.latitude,
                "merchant_lng": merchant.longitude,
                "delivery_address": order.delivery_address,
                "total_amount": order.total_amount,
                "delivery_fee": order.delivery_fee,
                "driver_earnings": _driver_earnings(order.delivery_fee, driver.rating),
                "is_peak": _is_peak_hour(),
                "items_count": len(order.items) if order.items else 0,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
            for order, merchant in result.fetchall()
        ]
    }


@router.post("/orders/{order_id}/accept")
async def accept_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    if driver.status != "available":
        raise HTTPException(status_code=400, detail="يجب أن تكون متاحاً لقبول الطلبات")

    existing = await db.execute(
        select(Order).where(
            and_(
                Order.driver_id == driver.id,
                Order.status.in_([OrderStatus.READY_FOR_PICKUP, OrderStatus.ON_THE_WAY]),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="لديك طلب نشط بالفعل")

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    if str(order.status) != OrderStatus.READY_FOR_PICKUP:
        raise HTTPException(status_code=400, detail="الطلب لم يعد متاحاً")
    if order.driver_id is not None:
        raise HTTPException(status_code=400, detail="تم أخذ الطلب من قبل سائق آخر")

    order.driver_id = driver.id
    driver.status = "busy"
    await db.commit()

    # Notify other drivers that this order is taken
    await driver_ws.broadcast_new_order(
        {"id": str(order.id), "__taken": True},
        driver_ws.connected_ids - {str(driver.id)},
    )

    return {"ok": True, "order_id": str(order.id)}


@router.post("/orders/{order_id}/reject")
async def reject_order(order_id: str, current_user: User = Depends(require_driver)):
    return {"ok": True}


@router.get("/orders/current")
async def get_current_order(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    result = await db.execute(
        select(Order, Merchant)
        .join(Merchant, Order.merchant_id == Merchant.id)
        .where(
            and_(
                Order.driver_id == driver.id,
                Order.status.in_([OrderStatus.READY_FOR_PICKUP, OrderStatus.ON_THE_WAY]),
            )
        )
        .order_by(desc(Order.created_at))
        .limit(1)
    )
    row = result.first()
    if not row:
        return {"order": None}

    order, merchant = row
    customer_res = await db.execute(select(User).where(User.id == order.customer_id))
    customer = customer_res.scalar_one_or_none()

    return {
        "order": {
            "id": str(order.id),
            "order_number": order.order_number,
            "status": str(order.status),
            "merchant_name": merchant.name_ar or merchant.name,
            "merchant_lat": merchant.latitude,
            "merchant_lng": merchant.longitude,
            "merchant_phone": merchant.phone,
            "delivery_address": order.delivery_address,
            "customer_name": customer.full_name if customer else "",
            "customer_phone": customer.phone if customer else "",
            "total_amount": order.total_amount,
            "delivery_fee": order.delivery_fee,
            "driver_earnings": _driver_earnings(order.delivery_fee, driver.rating),
            "items": [
                {
                    "name": (item.product.name_ar or item.product.name) if item.product else "",
                    "quantity": item.quantity,
                }
                for item in (order.items or [])
            ],
        }
    }


@router.put("/orders/{order_id}/step")
async def update_order_step(
    order_id: str,
    payload: StepUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    if str(order.driver_id) != str(driver.id):
        raise HTTPException(status_code=403, detail="هذا ليس طلبك")

    current_status = str(order.status)

    if payload.step == "at_store":
        pass

    elif payload.step == "picked_up":
        if current_status != OrderStatus.READY_FOR_PICKUP:
            raise HTTPException(status_code=400, detail="الطلب ليس في حالة جاهز للاستلام")
        order.status = OrderStatus.ON_THE_WAY

    elif payload.step == "delivered":
        if current_status != OrderStatus.ON_THE_WAY:
            raise HTTPException(status_code=400, detail="يجب أن يكون الطلب في الطريق")
        order.status = OrderStatus.DELIVERED
        driver.status = "available"
        driver.total_deliveries += 1
        earned = _driver_earnings(order.delivery_fee, driver.rating)
        driver.total_earnings += earned

        # Record earning transaction
        await _record_tx(db, driver.id, "earning", earned,
                         f"توصيلة #{order.order_number}", str(order.id))

        # Check daily target incentive
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        count_res = await db.execute(
            select(func.count(Order.id)).where(
                and_(
                    Order.driver_id == driver.id,
                    Order.status == OrderStatus.DELIVERED,
                    Order.updated_at >= today,
                )
            )
        )
        today_count = int(count_res.scalar() or 0) + 1  # +1 for this delivery

        for tier in DAILY_TARGETS:
            if today_count == tier["target"]:
                bonus = tier["bonus"]
                driver.total_earnings += bonus
                await _record_tx(db, driver.id, "bonus", bonus,
                                 f"🏆 {tier['label']} — {tier['target']} توصيلة اليوم")
                break
    else:
        raise HTTPException(status_code=400, detail="خطوة غير صالحة")

    await db.commit()
    return {"ok": True, "order_status": str(order.status), "driver_status": driver.status}


# ── Earnings ──────────────────────────────────────────────────────────────────

@router.get("/earnings")
async def get_earnings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    async def period_stats(start: datetime):
        r = await db.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.delivery_fee), 0.0))
            .where(and_(
                Order.driver_id == driver.id,
                Order.status == OrderStatus.DELIVERED,
                Order.updated_at >= start,
            ))
        )
        row = r.first()
        return int(row[0] or 0), round(float(row[1] or 0) * 0.8, 2)

    today_count, today_earn = await period_stats(today_start)
    week_count,  week_earn  = await period_stats(week_start)
    month_count, month_earn = await period_stats(month_start)

    # Incentive progress
    incentives = []
    for tier in DAILY_TARGETS:
        remaining = max(0, tier["target"] - today_count)
        incentives.append({
            "label": tier["label"],
            "target": tier["target"],
            "progress": today_count,
            "remaining": remaining,
            "bonus": tier["bonus"],
            "achieved": today_count >= tier["target"],
        })

    # Rating bonus
    rating_bonus = None
    for rb in RATING_BONUSES:
        if driver.rating >= rb["min_rating"]:
            rating_bonus = {"label": rb["label"], "pct": int(rb["pct"] * 100)}
            break

    return {
        "total_earnings":   driver.total_earnings,
        "total_deliveries": driver.total_deliveries,
        "rating":           driver.rating,
        "is_peak":          _is_peak_hour(),
        "rating_bonus":     rating_bonus,
        "today":  {"orders": today_count, "earnings": today_earn},
        "week":   {"orders": week_count,  "earnings": week_earn},
        "month":  {"orders": month_count, "earnings": month_earn},
        "incentives": incentives,
    }


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history")
async def get_history(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    total = int((await db.execute(
        select(func.count(Order.id)).where(
            and_(Order.driver_id == driver.id, Order.status == OrderStatus.DELIVERED)
        )
    )).scalar() or 0)

    result = await db.execute(
        select(Order, Merchant)
        .join(Merchant, Order.merchant_id == Merchant.id)
        .where(and_(Order.driver_id == driver.id, Order.status == OrderStatus.DELIVERED))
        .order_by(desc(Order.updated_at))
        .limit(limit).offset(offset)
    )

    return {
        "total": total,
        "orders": [
            {
                "id": str(order.id),
                "order_number": order.order_number,
                "merchant_name": merchant.name_ar or merchant.name,
                "total_amount": order.total_amount,
                "driver_earnings": round(order.delivery_fee * 0.8, 2),
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "delivered_at": order.updated_at.isoformat() if order.updated_at else None,
            }
            for order, merchant in result.fetchall()
        ],
    }


# ── Wallet ────────────────────────────────────────────────────────────────────

@router.get("/wallet")
async def get_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))

    # Pending withdrawal
    pending_res = await db.execute(
        select(func.coalesce(func.sum(DriverTransaction.amount), 0.0))
        .where(and_(
            DriverTransaction.driver_id == driver.id,
            DriverTransaction.tx_type == "withdrawal",
            DriverTransaction.status == "pending",
        ))
    )
    pending_withdrawal = abs(float(pending_res.scalar() or 0))

    # Recent transactions
    tx_res = await db.execute(
        select(DriverTransaction)
        .where(DriverTransaction.driver_id == driver.id)
        .order_by(desc(DriverTransaction.created_at))
        .limit(30)
    )
    txs = tx_res.scalars().all()

    return {
        "balance": driver.total_earnings,
        "pending_withdrawal": pending_withdrawal,
        "available_for_withdrawal": max(0.0, driver.total_earnings - pending_withdrawal),
        "transactions": [
            {
                "id": str(t.id),
                "type": t.tx_type,
                "amount": t.amount,
                "description": t.description,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in txs
        ],
    }


@router.post("/wallet/withdraw")
async def request_withdrawal(
    payload: WithdrawalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    if payload.amount < 500:
        raise HTTPException(status_code=400, detail="الحد الأدنى للسحب 500 ر.ي")
    if payload.amount > driver.total_earnings:
        raise HTTPException(status_code=400, detail="الرصيد غير كافٍ")

    await _record_tx(
        db, driver.id, "withdrawal", -payload.amount,
        f"طلب سحب{' — ' + payload.notes if payload.notes else ''}",
        status="pending",
    )
    await db.commit()
    return {"ok": True, "message": "تم إرسال طلب السحب، سيتم المعالجة خلال 24 ساعة"}


# ── Documents ─────────────────────────────────────────────────────────────────

DOC_LABELS = {
    "id_card": "بطاقة الهوية",
    "license": "رخصة القيادة",
    "vehicle_front": "صورة المركبة (أمام)",
    "vehicle_back": "صورة المركبة (خلف)",
    "selfie": "صورة شخصية",
}

@router.get("/documents")
async def get_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    driver = await _get_driver(db, str(current_user.id))
    result = await db.execute(
        select(DriverDocument)
        .where(DriverDocument.driver_id == driver.id)
        .order_by(DriverDocument.created_at)
    )
    docs = result.scalars().all()
    return {
        "documents": [
            {
                "id": str(d.id),
                "doc_type": d.doc_type,
                "label": DOC_LABELS.get(d.doc_type, d.doc_type),
                "file_url": d.file_url,
                "status": d.status,
                "notes": d.notes,
            }
            for d in docs
        ],
        "required": list(DOC_LABELS.keys()),
    }


@router.post("/documents/upload")
async def upload_document(
    doc_type: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_driver),
):
    if doc_type not in DOC_LABELS:
        raise HTTPException(status_code=400, detail="نوع المستند غير صالح")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="نوع الملف غير مسموح به")

    filename = f"driver_doc_{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOADS_DIR, filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    file_url = f"/uploads/{filename}"

    driver = await _get_driver(db, str(current_user.id))

    # Replace existing doc of same type
    existing = await db.execute(
        select(DriverDocument).where(
            and_(DriverDocument.driver_id == driver.id, DriverDocument.doc_type == doc_type)
        )
    )
    ex_doc = existing.scalar_one_or_none()
    if ex_doc:
        ex_doc.file_url = file_url
        ex_doc.status = "pending"
        ex_doc.notes = None
    else:
        db.add(DriverDocument(driver_id=driver.id, doc_type=doc_type, file_url=file_url))

    await db.commit()
    return {"ok": True, "file_url": file_url}
