from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.models.address import Address

router = APIRouter(prefix="/users", tags=["users"])


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    preferred_language: Optional[str] = None
    fcm_token: Optional[str] = None


class AddressCreate(BaseModel):
    label: str = "Home"
    full_address: str
    city: str
    district: Optional[str] = None
    street: Optional[str] = None
    latitude: float
    longitude: float
    building_number: Optional[str] = None
    notes: Optional[str] = None
    is_default: bool = False


@router.get("/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "phone": current_user.phone,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role,
        "status": current_user.status,
        "profile_image_url": current_user.profile_image_url,
        "preferred_language": current_user.preferred_language,
        "is_phone_verified": current_user.is_phone_verified,
        "addresses": [_serialize_address(a) for a in (current_user.addresses or [])],
    }


@router.patch("/me")
async def update_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.full_name:
        current_user.full_name = payload.full_name
    if payload.email:
        current_user.email = payload.email
    if payload.preferred_language:
        current_user.preferred_language = payload.preferred_language
    if payload.fcm_token:
        current_user.fcm_token = payload.fcm_token
    return {"message": "Profile updated"}


@router.post("/me/addresses", status_code=201)
async def add_address(
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.is_default:
        existing = await db.execute(
            select(Address).where(Address.user_id == current_user.id, Address.is_default == True)
        )
        for addr in existing.scalars().all():
            addr.is_default = False

    address = Address(
        user_id=current_user.id,
        label=payload.label,
        full_address=payload.full_address,
        city=payload.city,
        district=payload.district,
        street=payload.street,
        latitude=payload.latitude,
        longitude=payload.longitude,
        building_number=payload.building_number,
        notes=payload.notes,
        is_default=payload.is_default,
    )
    db.add(address)
    await db.flush()
    await db.refresh(address)
    return _serialize_address(address)


@router.delete("/me/addresses/{address_id}")
async def delete_address(
    address_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == current_user.id)
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    await db.delete(address)
    return {"message": "Address deleted"}


def _serialize_address(a: Address) -> dict:
    return {
        "id": str(a.id),
        "label": a.label,
        "full_address": a.full_address,
        "city": a.city,
        "district": a.district,
        "latitude": a.latitude,
        "longitude": a.longitude,
        "is_default": a.is_default,
    }
