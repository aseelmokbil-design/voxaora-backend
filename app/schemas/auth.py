from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re


class RegisterRequest(BaseModel):
    phone: str
    full_name: str
    password: str
    email: Optional[EmailStr] = None
    preferred_language: str = "ar"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 9:
            raise ValueError("Invalid phone number")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserBrief"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserBrief(BaseModel):
    id: str
    phone: str
    full_name: str
    email: Optional[str]
    role: str
    status: str
    profile_image_url: Optional[str]
    preferred_language: str

    class Config:
        from_attributes = True
