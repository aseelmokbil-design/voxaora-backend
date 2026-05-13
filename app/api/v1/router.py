from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, merchants, orders, voice, admin, driver
from app.api.v1.endpoints import intelligence, notifications, stats, deals, coupons

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(merchants.router)
api_router.include_router(orders.router)
api_router.include_router(voice.router)
api_router.include_router(admin.router)
api_router.include_router(driver.router)
api_router.include_router(intelligence.router)
api_router.include_router(notifications.router)
api_router.include_router(stats.router)
api_router.include_router(deals.router)
api_router.include_router(coupons.router)
