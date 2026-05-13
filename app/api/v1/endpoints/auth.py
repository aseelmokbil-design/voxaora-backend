from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.models.user import User, UserRole, UserStatus
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, UserBrief

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_brief(user: User) -> UserBrief:
    return UserBrief(
        id=str(user.id),
        phone=user.phone,
        full_name=user.full_name,
        email=user.email,
        role=str(user.role),
        status=str(user.status),
        profile_image_url=user.profile_image_url,
        preferred_language=user.preferred_language,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.phone == payload.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    user = User(
        phone=payload.phone,
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        preferred_language=payload.preferred_language,
        role=UserRole.CUSTOMER.value,
        status=UserStatus.ACTIVE.value,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token_data = {"sub": str(user.id), "role": str(user.role)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_user_brief(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.phone == payload.phone))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    if user.status == UserStatus.SUSPENDED or user.status == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended")

    user.last_login_at = datetime.now(timezone.utc)

    token_data = {"sub": str(user.id), "role": str(user.role)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_user_brief(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == data["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    token_data = {"sub": str(user.id), "role": str(user.role)}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_user_brief(user),
    )
