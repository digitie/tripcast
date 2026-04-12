"""여행 리포트 생성 및 텔레그램 전송 핵심 로직.

Airflow DAG 와 FastAPI 양쪽에서 import 해서 사용한다.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Iterable

from geoalchemy2 import Geography
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    FuelPrice,
    FuelStation,
    NotificationLog,
    RestStop,
    RestStopWeather,
    Trip,
    TripPlace,
    WeatherForecast,
)
from .telegram import TelegramClient


# --- 조회 헬퍼 -----------------------------------------------------------


def _point(lat: float, lon: float):
    """lat/lon -> geography(Point, 4326)."""
    return func.cast(ST_SetSRID(ST_MakePoint(lon, lat), 4326), Geography)


def nearest_rest_stop(db: Session, lat: float, lon: float, radius_m: int = 30000) -> RestStop | None:
    pt = _point(lat, lon)
    row = db.scalar(
        select(RestStop)
        .where(RestStop.location.isnot(None))
        .where(ST_DWithin(RestStop.location, pt, radius_m))
        .order_by(func.ST_Distance(RestStop.location, pt))
        .limit(1)
    )
    return row


def latest_rest_stop_weather(db: Session, rest_stop_id: int) -> RestStopWeather | None:
    return db.scalar(
        select(RestStopWeather)
        .where(RestStopWeather.rest_stop_id == rest_stop_id)
        .order_by(RestStopWeather.observed_at.desc())
        .limit(1)
    )


def fuel_prices_near(
    db: Session, lat: float, lon: float, radius_m: int = 10000
) -> dict[str, float | None]:
    """반경 내 주유소의 최근 유가 평균 (경유/휘발유/고급유)."""
    pt = _point(lat, lon)

    # 각 주유소의 최신 관측 1건만 골라 평균 (window/subquery).
    latest = (
        select(
            FuelPrice.station_id.label("station_id"),
            func.max(FuelPrice.observed_at).label("observed_at"),
        )
        .group_by(FuelPrice.station_id)
        .subquery()
    )

    stmt = (
        select(
            func.avg(FuelPrice.gasoline),
            func.avg(FuelPrice.premium_gasoline),
            func.avg(FuelPrice.diesel),
            func.count(FuelPrice.id),
        )
        .select_from(FuelPrice)
        .join(
            latest,
            and_(
                FuelPrice.station_id == latest.c.station_id,
                FuelPrice.observed_at == latest.c.observed_at,
            ),
        )
        .join(FuelStation, FuelStation.id == FuelPrice.station_id)
        .where(FuelStation.location.isnot(None))
        .where(ST_DWithin(FuelStation.location, pt, radius_m))
    )
    gas, prem, diesel, n = db.execute(stmt).one()
    return {
        "gasoline": float(gas) if gas is not None else None,
        "premium_gasoline": float(prem) if prem is not None else None,
        "diesel": float(diesel) if diesel is not None else None,
        "station_count": int(n or 0),
    }


def forecasts_for_day(
    db: Session, nx: int, ny: int, target_date: date, kind: str
) -> list[WeatherForecast]:
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return list(
        db.scalars(
            select(WeatherForecast)
            .where(
                WeatherForecast.nx == nx,
                WeatherForecast.ny == ny,
                WeatherForecast.kind == kind,
                WeatherForecast.forecast_at >= start,
                WeatherForecast.forecast_at < end,
            )
            .order_by(WeatherForecast.forecast_at.asc())
        )
    )


# --- 리포트 생성 ---------------------------------------------------------


@dataclass
class PlaceReport:
    place: TripPlace
    header: str
    forecast_lines: list[str]
    rest_stop_line: str | None
    fuel_line: str | None


def _fmt_day_forecast(fcs: list[WeatherForecast]) -> list[str]:
    if not fcs:
        return ["    (예보 데이터 없음)"]
    temps = [f.temperature for f in fcs if f.temperature is not None]
    rains = [f.precipitation or 0 for f in fcs]
    skies = [f.sky for f in fcs if f.sky]
    lines = []
    if temps:
        lines.append(f"    최저 {min(temps):.0f}℃ / 최고 {max(temps):.0f}℃")
    if rains and any(r for r in rains):
        lines.append(f"    총 강수량 ~ {sum(rains):.1f}mm")
    if skies:
        # 가장 많이 나온 sky
        common = max(set(skies), key=skies.count)
        lines.append(f"    하늘: {common}")
    return lines or ["    (예보 데이터 없음)"]


def _fmt_hourly(fcs: list[WeatherForecast]) -> list[str]:
    if not fcs:
        return ["    (초단기 예보 없음)"]
    lines = []
    for f in fcs:
        hh = f.forecast_at.astimezone().strftime("%H시")
        parts = [hh]
        if f.temperature is not None:
            parts.append(f"{f.temperature:.0f}℃")
        if f.sky:
            parts.append(f.sky)
        if f.pty and f.pty not in ("없음", "0"):
            parts.append(f.pty)
        if f.precipitation:
            parts.append(f"{f.precipitation:.1f}mm")
        lines.append("    " + " · ".join(parts))
    return lines


def build_place_report(
    db: Session,
    place: TripPlace,
    target_date: date,
    hourly: bool,
) -> PlaceReport:
    header = f"📍 <b>{place.sido} {place.sigungu}</b>" + (f" - {place.name}" if place.name else "")

    forecast_lines: list[str] = []
    if place.nx is not None and place.ny is not None:
        if hourly:
            fcs = forecasts_for_day(db, place.nx, place.ny, target_date, "ultra")
            forecast_lines = _fmt_hourly(fcs)
        else:
            fcs = forecasts_for_day(db, place.nx, place.ny, target_date, "short") or forecasts_for_day(
                db, place.nx, place.ny, target_date, "mid"
            )
            forecast_lines = _fmt_day_forecast(fcs)
    else:
        forecast_lines = ["    (격자 좌표 없음 - 좌표 매핑 필요)"]

    rest_stop_line: str | None = None
    fuel_line: str | None = None
    if place.location is not None:
        from geoalchemy2.shape import to_shape

        pt = to_shape(place.location)
        lat, lon = pt.y, pt.x

        rs = nearest_rest_stop(db, lat, lon)
        if rs is not None:
            rsw = latest_rest_stop_weather(db, rs.id)
            if rsw:
                rest_stop_line = (
                    f"🛣️ 인접 휴게소 '{rs.name}' {rsw.temperature:.0f}℃"
                    if rsw.temperature is not None
                    else f"🛣️ 인접 휴게소 '{rs.name}'"
                )
            else:
                rest_stop_line = f"🛣️ 인접 휴게소 '{rs.name}'"

        fuel = fuel_prices_near(db, lat, lon, radius_m=10000)
        if fuel["station_count"] > 0:
            fuel_line = (
                f"⛽ 반경 10km 평균 ({fuel['station_count']}개소) "
                f"휘발유 {fuel['gasoline']:.0f} · "
                f"경유 {fuel['diesel']:.0f} · "
                f"고급유 {fuel['premium_gasoline']:.0f}"
                if all(fuel[k] is not None for k in ("gasoline", "diesel", "premium_gasoline"))
                else f"⛽ 반경 10km 내 {fuel['station_count']}개 주유소"
            )

    return PlaceReport(
        place=place,
        header=header,
        forecast_lines=forecast_lines,
        rest_stop_line=rest_stop_line,
        fuel_line=fuel_line,
    )


def build_trip_message(db: Session, trip: Trip, target_date: date, hourly: bool) -> str:
    mode = "시간별 상세" if hourly else "일자별"
    title = f"🧳 <b>{trip.title}</b>\n🗓 {target_date.isoformat()} {mode} 리포트"

    places_for_day = [p for p in trip.places if p.visit_date == target_date]
    if not places_for_day:
        return title + "\n\n등록된 장소가 없습니다."

    # 날짜 별 장소 여러곳 지원 -> order_index 순 정렬
    places_for_day.sort(key=lambda p: (p.order_index, p.id))

    chunks = [title, ""]
    for p in places_for_day:
        rep = build_place_report(db, p, target_date, hourly)
        chunks.append(rep.header)
        chunks.extend(rep.forecast_lines)
        if rep.rest_stop_line:
            chunks.append("    " + rep.rest_stop_line)
        if rep.fuel_line:
            chunks.append("    " + rep.fuel_line)
        chunks.append("")
    return "\n".join(chunks).rstrip()


def iter_trips_needing_notification(db: Session, now: datetime) -> Iterable[tuple[Trip, date, bool]]:
    """여행 시작 N일 전 ~ 여행 종료일 까지 알림 대상을 산출.

    - 여행 1일 전 / 여행 중 : hourly=True (초단기 예보 기반)
    - 그 외 (2 ~ notify_lead_days 일 전) : hourly=False (단기/중기)
    """
    today = now.date()
    trips = db.scalars(
        select(Trip)
        .where(Trip.telegram_enabled.is_(True))
        .options(selectinload(Trip.places))
    ).all()

    for trip in trips:
        # lead day 시점부터 end_date 까지 매일 1회 발송
        first_notify = trip.start_date - timedelta(days=trip.notify_lead_days)
        if today < first_notify or today > trip.end_date:
            continue
        # 리포트 대상 날짜: 오늘이 여행 이전이라면 start_date 부터,
        # 여행 중이라면 오늘 해당 일자.
        if today < trip.start_date:
            target_date = trip.start_date
        else:
            target_date = today
        hourly = (trip.start_date - today).days <= 1 or trip.start_date <= today <= trip.end_date
        yield trip, target_date, hourly


def send_trip_reports(db: Session, telegram: TelegramClient, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    sent = 0
    for trip, target_date, hourly in iter_trips_needing_notification(db, now):
        chat_id = trip.telegram_chat_id or trip.user.telegram_chat_id
        if not chat_id:
            continue
        msg = build_trip_message(db, trip, target_date, hourly)
        log = NotificationLog(
            trip_id=trip.id,
            user_id=trip.user_id,
            kind="hourly" if hourly else "daily",
            target_date=target_date,
            message=msg,
        )
        try:
            telegram.send_message(chat_id, msg)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            log.success = False
            log.error = str(exc)[:500]
        db.add(log)
        db.commit()
    return sent
