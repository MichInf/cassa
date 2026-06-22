"""Modelli Pydantic per request/response delle API.

I totali (line_total_cents, total_cents) NON sono mai accettati dal client:
vengono calcolati lato server a partire dai prezzi correnti in DB.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProductIn(BaseModel):
    name: str = Field(min_length=1)
    category: str = "Generale"
    price_cents: int = Field(ge=0)
    active: bool = True
    sort_order: int = 0


class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    price_cents: int
    active: bool
    sort_order: int


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)
    note: str | None = None


class OrderItemOut(BaseModel):
    product_id: int | None
    product_name: str
    quantity: int
    unit_price_cents: int
    line_total_cents: int


class OrderOut(BaseModel):
    id: int
    created_at: str
    total_cents: int
    printed: bool
    note: str | None = None
    items: list[OrderItemOut] = []


class SettingsOut(BaseModel):
    association_name: str
    event_name: str
    footer_message: str
    printer_mode: str
    # admin_pin volutamente NON esposto in lettura


class SettingsIn(BaseModel):
    association_name: str | None = None
    event_name: str | None = None
    footer_message: str | None = None
    printer_mode: str | None = None
    admin_pin: str | None = None


class PrintResult(BaseModel):
    ok: bool
    mode: str
    detail: str | None = None
