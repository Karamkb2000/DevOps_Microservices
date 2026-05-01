"""Pydantic schemas for request/response validation."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    """Shared fields for product create/update payloads."""

    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: float = Field(..., ge=0)
    stock: int = Field(0, ge=0)


class ProductCreate(ProductBase):
    """Payload for creating a new product."""

    pass


class ProductUpdate(BaseModel):
    """Payload for partially updating a product. All fields optional."""

    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    price: Optional[float] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)


class ProductResponse(ProductBase):
    """Response payload for a product."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True
