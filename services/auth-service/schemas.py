"""Pydantic schemas for the auth-service."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=100)


class UserResponse(BaseModel):
    """Public representation of a user."""

    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True


class Token(BaseModel):
    """JWT token returned to clients on successful login."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Internal representation of the data carried inside a JWT."""

    email: Optional[str] = None


class LoginRequest(BaseModel):
    """Payload for the JSON login endpoint."""

    email: str
    password: str
