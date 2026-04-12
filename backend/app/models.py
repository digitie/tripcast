"""SQLAlchemy 2.0 ORM 모델.

시군구 단위까지의 장소를 PostGIS POINT 로 저장하며, 반경 질의는
ST_DWithin (geography) 을 사용한다.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# --- users ---------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 텔레그램 노티 기본값 - 사용자별로 연결된 채팅ID / 활성화여부
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    trips: Mapped[list["Trip"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# --- trips ---------------------------------------------------------------


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 이 여행에 대한 텔레그램 알림 override 정보
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_lead_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="trips")
    places: Mapped[list["TripPlace"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripPlace.visit_date",
    )


class TripPlace(Base):
    """여행 날짜 별 장소.  한 날짜에 여러 장소 등록 가능."""

    __tablename__ = "trip_places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)

    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 행정구역 (시군구 단위까지)
    sido: Mapped[str] = mapped_column(String(40), nullable=False)       # 예: 강원특별자치도
    sigungu: Mapped[str] = mapped_column(String(60), nullable=False)    # 예: 강릉시
    # 상세 장소명 (선택)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # 기상청 동네예보 격자 좌표 (nx, ny)
    nx: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ny: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 위/경도 (EPSG:4326, geography for meter-based ST_DWithin)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)

    trip: Mapped[Trip] = relationship(back_populates="places")


# --- 휴게소 & 날씨 캐시 --------------------------------------------------


class RestStop(Base):
    """전국 휴게소. data.go.kr 한국도로공사 공개API 로 받아 월 1회 업데이트."""

    __tablename__ = "rest_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    route_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sido: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    sigungu: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True, index=True
    )

    raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RestStopWeather(Base):
    """휴게소 날씨 스냅샷 (1시간 단위 이상의 최신 값을 저장)."""

    __tablename__ = "rest_stop_weather"
    __table_args__ = (
        UniqueConstraint("rest_stop_id", "observed_at", name="uq_rest_stop_obs"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rest_stop_id: Mapped[int] = mapped_column(ForeignKey("rest_stops.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precipitation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sky: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class WeatherForecast(Base):
    """여행지 (nx,ny) 기준 단기/중기/초단기 예보 캐시.

    kind: "ultra" (초단기, ~6h), "short" (단기, ~3일), "mid" (중기, 3~10일)
    """

    __tablename__ = "weather_forecasts"
    __table_args__ = (
        UniqueConstraint("nx", "ny", "forecast_at", "kind", name="uq_fcst_grid_time"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nx: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ny: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    base_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    forecast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sky: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pty: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    precipitation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- 주유소 유가 --------------------------------------------------------


class FuelStation(Base):
    __tablename__ = "fuel_stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sido: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    sigungu: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True, index=True
    )
    raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FuelPrice(Base):
    """주유소별 기름값. 하루 3회 저장(cron: 06/14/22)."""

    __tablename__ = "fuel_prices"
    __table_args__ = (
        UniqueConstraint("station_id", "observed_at", name="uq_station_obs"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("fuel_stations.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gasoline: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # 휘발유
    premium_gasoline: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 고급유
    diesel: Mapped[Optional[float]] = mapped_column(Float, nullable=True)     # 경유
    raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


# --- 알림 로그 ----------------------------------------------------------


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # daily | hourly
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
