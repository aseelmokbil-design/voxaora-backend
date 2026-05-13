from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole, UserStatus

bearer_scheme = HTTPBearer()

_ADMIN_ROLES = {UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value}
_MERCHANT_ROLES = {UserRole.MERCHANT.value, UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value}
_DRIVER_ROLES = {UserRole.DRIVER.value, UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("No subject in token")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if str(user.status) == UserStatus.SUSPENDED.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if str(current_user.role) not in _ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


async def require_merchant(current_user: User = Depends(get_current_user)) -> User:
    if str(current_user.role) not in _MERCHANT_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Merchant access required")
    return current_user


async def require_driver(current_user: User = Depends(get_current_user)) -> User:
    if str(current_user.role) not in _DRIVER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver access required")
    return current_user
