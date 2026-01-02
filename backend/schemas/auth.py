import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


def validate_password_strength(password: str) -> str:
    """
    Shared password validation rules.

    Rules:
    - at least 8 characters
    - at least one lowercase letter
    - at least one uppercase letter
    - at least one number
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one number")
    return password


class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Username must be at most 50 characters long")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, and underscores"
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class MessageResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    """Request schema for changing password."""

    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ForgotPasswordRequest(BaseModel):
    """Request schema for forgot password."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request schema for resetting password with token."""

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class AccountDeleteRequest(BaseModel):
    """Request schema for account deletion.

    Requires both password verification and explicit confirmation
    to prevent accidental account deletion.
    """

    password: str
    confirmation: str

    @field_validator("confirmation")
    @classmethod
    def validate_confirmation(cls, v: str) -> str:
        """Ensure confirmation is exactly 'DELETE' (case-sensitive)."""
        if v != "DELETE":
            raise ValueError("Confirmation must be exactly 'DELETE'")
        return v


class DeviceUpdateRequest(BaseModel):
    """Request schema for updating device metadata."""

    device_name: Optional[str] = None
    platform: Optional[str] = None  # "ios", "android", "web"
    app_version: Optional[str] = None


class DeviceResponse(BaseModel):
    """Response schema for device data."""

    id: int
    device_uuid: Optional[str]
    device_name: Optional[str]
    platform: Optional[str]
    app_version: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

