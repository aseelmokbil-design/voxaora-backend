"""
Real-time order tracking via WebSocket + REST snapshot.
Simulates driver movement for demo orders (no real driver hardware needed).
"""
import asyncio
import json
import math
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.order import Order, OrderStatus
from app.models.merchant import Merchant
from app.models.voice_session import VoiceSession
from app.models.user import User
import structlog

logger = structlog.get_logger()
router = APIRouter(tags=["tracking"])

# Seconds each status lasts before auto-advancing (demo simulation)
STATUS_DURATIONS = {
    OrderStatus.PENDING:          8,
    OrderStatus.CONFIRMED:        12,
    OrderStatus.PREPARING:        28,
    OrderStatus.READY_FOR_PICKUP: 5,
    OrderStatus.PICKED_UP:        4,
    OrderStatus.ON_THE_WAY:       35,
}

STATUS_SEQUENCE = [
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARING,
    OrderStatus.READY_FOR_PICKUP,
    OrderStatus.PICKED_UP,
    OrderStatus.ON_THE_WAY,
    OrderStatus.DELIVERED,
]


def _next_status(current: str) -> Optional[str]:
    try:
        idx = STATUS_SEQUENCE.index(current)
        if idx < len(STATUS_SEQUENCE) - 1:
            return STATUS_SEQUENCE[idx + 1]
    except ValueError:
        pass
    return None


def _interpolate(a: float, b: float, t: float) -> float:
    """Linear interpolation, t clamped to [0,1]."""
    t = max(0.0, min(1.0, t))
    return a + (b - a) * t


def _driver_position(
    status: str,
    elapsed_in_status: float,
    merchant_lat: float, merchant_lng: float,
    customer_lat: float, customer_lng: float,
    heading_lat: float, heading_lng: float,   # driver's "staging" position
) -> tuple[float, float]:
    """Return simulated driver (lat, lng) based on current status."""
    if status in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
        # Driver not yet assigned → show near merchant (staging area)
        return heading_lat, heading_lng

    if status == OrderStatus.PREPARING:
        # Driver heading toward merchant
        t = elapsed_in_status / STATUS_DURATIONS.get(OrderStatus.PREPARING, 28)
        return (
            _interpolate(heading_lat, merchant_lat, t),
            _interpolate(heading_lng, merchant_lng, t),
        )

    if status in (OrderStatus.READY_FOR_PICKUP, OrderStatus.PICKED_UP):
        return merchant_lat, merchant_lng

    if status == OrderStatus.ON_THE_WAY:
        t = elapsed_in_status / STATUS_DURATIONS.get(OrderStatus.ON_THE_WAY, 35)
        return (
            _interpolate(merchant_lat, customer_lat, t),
            _interpolate(merchant_lng, customer_lng, t),
        )

    if status == OrderStatus.DELIVERED:
        return customer_lat, customer_lng

    return merchant_lat, merchant_lng


def _eta_minutes(status: str, elapsed_in_status: float) -> int:
    remaining_in_current = max(0, STATUS_DURATIONS.get(status, 0) - elapsed_in_status)
    later_statuses_time = sum(
        STATUS_DURATIONS.get(s, 0)
        for s in STATUS_SEQUENCE[STATUS_SEQUENCE.index(status) + 1 :]
        if s != OrderStatus.DELIVERED
    ) if status in STATUS_SEQUENCE else 0
    total_seconds = remaining_in_current + later_statuses_time
    return max(1, math.ceil(total_seconds / 60))


async def _resolve_order(db: AsyncSession, order_id: str, user_id: str):
    """Fetch order and verify ownership."""
    result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return None
    if str(order.customer_id) != user_id:
        return None
    return order


async def _get_merchant(db: AsyncSession, merchant_id: str) -> Optional[Merchant]:
    result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
    return result.scalar_one_or_none()


async def _get_customer_location(db: AsyncSession, order: Order) -> tuple[float, float]:
    """Try to get customer location from voice session or delivery address."""
    # Try voice session first
    if order.voice_session_id:
        r = await db.execute(
            select(VoiceSession).where(VoiceSession.id == order.voice_session_id)
        )
        vs = r.scalar_one_or_none()
        if vs and vs.user_latitude and vs.user_longitude:
            return float(vs.user_latitude), float(vs.user_longitude)

    # Try delivery address JSON
    addr = order.delivery_address or {}
    if isinstance(addr, dict) and addr.get("latitude") and addr.get("longitude"):
        return float(addr["latitude"]), float(addr["longitude"])

    # Fallback: ~2 km south-west of Riyadh center (demo customer)
    return 24.6935, 46.6506


# ── REST snapshot ─────────────────────────────────────────────────────────────

@router.get("/api/v1/orders/{order_id}/tracking")
async def get_tracking_snapshot(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public snapshot for initial map render (no auth — order_id is the secret)."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    merchant = await _get_merchant(db, str(order.merchant_id))
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")

    customer_lat, customer_lng = await _get_customer_location(db, order)

    # Staging position for driver (north-east of merchant by ~0.005 deg ≈ 500m)
    staging_lat = merchant.latitude + 0.005
    staging_lng = merchant.longitude + 0.005

    # Elapsed time estimate (uses created_at as anchor, not real per-status timer)
    elapsed_total = (time.time() - order.created_at.timestamp()) if order.created_at else 0
    elapsed_in_status = elapsed_total % 60   # approximation for snapshot

    driver_lat, driver_lng = _driver_position(
        status=str(order.status),
        elapsed_in_status=elapsed_in_status,
        merchant_lat=merchant.latitude,
        merchant_lng=merchant.longitude,
        customer_lat=customer_lat,
        customer_lng=customer_lng,
        heading_lat=staging_lat,
        heading_lng=staging_lng,
    )

    return {
        "status": str(order.status),
        "merchant_lat": merchant.latitude,
        "merchant_lng": merchant.longitude,
        "merchant_name": merchant.name_ar or merchant.name,
        "customer_lat": customer_lat,
        "customer_lng": customer_lng,
        "driver_lat": driver_lat,
        "driver_lng": driver_lng,
        "eta_minutes": _eta_minutes(str(order.status), elapsed_in_status),
        "order_number": order.order_number,
    }


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/orders/{order_id}")
async def order_tracking_ws(
    websocket: WebSocket,
    order_id: str,
    token: str = "",
):
    await websocket.accept()

    # Authenticate via query-param token
    user_id: Optional[str] = None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except Exception:
        await websocket.send_text(json.dumps({"type": "error", "detail": "unauthorized"}))
        await websocket.close(code=4001)
        return

    # Open a DB session for this WebSocket lifecycle
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        order = await _resolve_order(db, order_id, user_id)
        if not order:
            await websocket.send_text(json.dumps({"type": "error", "detail": "not_found"}))
            await websocket.close(code=4004)
            return

        merchant = await _get_merchant(db, str(order.merchant_id))
        if not merchant:
            await websocket.close()
            return

        customer_lat, customer_lng = await _get_customer_location(db, order)
        staging_lat = merchant.latitude + 0.005
        staging_lng = merchant.longitude + 0.005

        # Per-status timer: track when current status started
        status_start = time.time()
        current_status = str(order.status)

        logger.info("ws_tracking_connected", order=order_id, status=current_status)

        try:
            while True:
                now = time.time()
                elapsed_in_status = now - status_start

                # Auto-advance status for demo simulation
                terminal = current_status in (
                    OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED
                )
                if not terminal:
                    duration = STATUS_DURATIONS.get(current_status, 999)
                    if elapsed_in_status >= duration:
                        next_s = _next_status(current_status)
                        if next_s:
                            # Persist new status to DB
                            try:
                                result = await db.execute(
                                    select(Order).where(Order.id == order_id)
                                )
                                fresh = result.scalar_one_or_none()
                                if fresh and str(fresh.status) == current_status:
                                    fresh.status = next_s
                                    await db.commit()
                            except Exception as e:
                                logger.warning("ws_status_update_failed", error=str(e))
                                await db.rollback()

                            current_status = next_s
                            status_start = now
                            elapsed_in_status = 0.0

                driver_lat, driver_lng = _driver_position(
                    status=current_status,
                    elapsed_in_status=elapsed_in_status,
                    merchant_lat=merchant.latitude,
                    merchant_lng=merchant.longitude,
                    customer_lat=customer_lat,
                    customer_lng=customer_lng,
                    heading_lat=staging_lat,
                    heading_lng=staging_lng,
                )

                payload_out = {
                    "type": "tracking_update",
                    "status": current_status,
                    "merchant_lat": merchant.latitude,
                    "merchant_lng": merchant.longitude,
                    "merchant_name": merchant.name_ar or merchant.name,
                    "customer_lat": customer_lat,
                    "customer_lng": customer_lng,
                    "driver_lat": round(driver_lat, 6),
                    "driver_lng": round(driver_lng, 6),
                    "eta_minutes": _eta_minutes(current_status, elapsed_in_status),
                    "order_number": order.order_number,
                }

                await websocket.send_text(json.dumps(payload_out))

                if current_status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
                    await asyncio.sleep(2)
                    await websocket.close()
                    break

                await asyncio.sleep(3)

        except WebSocketDisconnect:
            logger.info("ws_tracking_disconnected", order=order_id)
        except Exception as e:
            logger.error("ws_tracking_error", order=order_id, error=str(e))
