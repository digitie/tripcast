"""Pydantic v2 스키마."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- auth / user ---------------------------------------------------------


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    telegram_chat_id: Optional[str] = None
    telegram_enabled: bool = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    telegram_chat_id: Optional[str] = None
    telegram_enabled: bool
    created_at: datetime


class UserUpdate(BaseModel):
    """사용자 정보 수정: 비밀번호 / 텔레그램 정보만 변경 가능."""

    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- trip ----------------------------------------------------------------


class TripPlaceIn(BaseModel):
    visit_date: date
    order_index: int = 0
    sido: str
    sigungu: str
    name: Optional[str] = None
    # 클라이언트에서 좌표를 제공하지 않으면 서버가 region_mapper 로 격자 변환
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # 이 장소의 주변 지역/유가 검색 반경(m). 기본 10,000m.
    radius_m: int = Field(default=10000, ge=500, le=100000)


class TripPlaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    visit_date: date
    order_index: int
    sido: str
    sigungu: str
    name: Optional[str] = None
    nx: Optional[int] = None
    ny: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_m: int = 10000


class TripCreate(BaseModel):
    title: str
    start_date: date
    end_date: date
    telegram_chat_id: Optional[str] = None
    telegram_enabled: bool = True
    notify_lead_days: int = 7
    places: list[TripPlaceIn] = Field(default_factory=list)


class TripUpdate(BaseModel):
    title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    notify_lead_days: Optional[int] = None
    places: Optional[list[TripPlaceIn]] = None


class TripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    start_date: date
    end_date: date
    telegram_chat_id: Optional[str] = None
    telegram_enabled: bool
    notify_lead_days: int
    places: list[TripPlaceOut] = Field(default_factory=list)
    created_at: datetime
