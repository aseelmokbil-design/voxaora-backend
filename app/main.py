from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import structlog
import time
import os

from app.core.config import settings
from app.api.v1.router import api_router
from app.api.v1.endpoints.tracking import router as tracking_router
from app.core.database import engine
from app.core.redis import close_redis

logger = structlog.get_logger()


UPLOADS_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("voxaora_startup", env=settings.APP_ENV)
    yield
    await close_redis()
    await engine.dispose()
    logger.info("voxaora_shutdown")


app = FastAPI(
    title="VOXAORA API",
    description="AI Voice Commerce Super App — Speak. Compare. Order.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration,
    )
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}


app.include_router(api_router)
app.include_router(tracking_router)   # WebSocket + tracking REST (no /api/v1 prefix)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
