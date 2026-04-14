"""주유소 유가 정보를 하루 3회 업데이트.

여행지의 위/경도 기준 반경 10km 의 주유소만 긁어와서 저장한다.
(전국 모든 주유소는 과도하므로 여행지 주변만 필요.)
"""
from __future__ import annotations

from datetime import datetime, timezone

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from _common import DATA_GO_KR_KEY, SessionLocal
from tripcast_app.models import FuelPrice, FuelStation, Trip, TripPlace
from tripcast_app.services.data_go_kr import DataGoKrClient


def _active_trip_points(session):
    """(lat, lon, radius_m) 리스트. 좌표는 소수 3자리 dedup, 반경은 max."""
    rows = session.scalars(
        select(Trip)
        .where(Trip.end_date >= datetime.now(tz=timezone.utc).date())
        .where(Trip.telegram_enabled.is_(True))
    ).all()
    points: dict[tuple[float, float], int] = {}
    for t in rows:
        for p in t.places:
            if p.location is None:
                continue
            pt = to_shape(p.location)
            key = (round(pt.y, 3), round(pt.x, 3))
            radius = p.radius_m or 10000
            points[key] = max(points.get(key, 0), radius)
    return [(lat, lon, r) for (lat, lon), r in points.items()]


def update_fuel_prices() -> None:
    if not DATA_GO_KR_KEY:
        print("DATA_GO_KR_KEY is empty, skip fuel update")
        return
    client = DataGoKrClient(service_key=DATA_GO_KR_KEY)
    now = datetime.now(tz=timezone.utc)
    with SessionLocal() as session:
        for lat, lon, radius_m in _active_trip_points(session):
            try:
                resp = client.get_fuel_prices_in_radius(lat, lon, radius_m=radius_m)
                items = _extract_items(resp)
                for item in items:
                    _upsert_station_and_price(session, item, observed_at=now)
            except Exception as e:  # noqa: BLE001
                print(f"fuel fetch failed for {lat},{lon} r={radius_m}: {e}")
        session.commit()


def _extract_items(resp: dict) -> list[dict]:
    # 엔드포인트 별 응답 구조가 다를 수 있으므로 방어적으로 파싱
    body = resp.get("response", {}).get("body", {}) or resp.get("body", {})
    items = body.get("items") or {}
    if isinstance(items, dict):
        items = items.get("item", [])
    return items or []


def _upsert_station_and_price(session, item: dict, observed_at: datetime) -> None:
    code = str(item.get("UNI_ID") or item.get("uni_id") or item.get("id") or "")
    if not code:
        return
    lat = _f(item.get("GIS_Y_COOR") or item.get("lat"))
    lon = _f(item.get("GIS_X_COOR") or item.get("lon"))

    station = session.scalar(select(FuelStation).where(FuelStation.external_code == code))
    if station is None:
        station = FuelStation(
            external_code=code,
            name=str(item.get("OS_NM") or item.get("name") or code),
            brand=str(item.get("POLL_DIV_CD") or item.get("brand") or ""),
            sido=str(item.get("SIDO_NM") or ""),
            sigungu=str(item.get("SIGUNGU_NM") or ""),
            latitude=lat,
            longitude=lon,
            location=from_shape(Point(lon, lat), srid=4326) if lat and lon else None,
            raw=item,
        )
        session.add(station)
        session.flush()
    else:
        station.raw = item
        if lat and lon:
            station.latitude = lat
            station.longitude = lon
            station.location = from_shape(Point(lon, lat), srid=4326)

    row = {
        "station_id": station.id,
        "observed_at": observed_at,
        "gasoline": _f(item.get("PRICE_GASOLINE") or item.get("gasoline")),
        "premium_gasoline": _f(item.get("PRICE_PREMIUM_GASOLINE") or item.get("premium_gasoline")),
        "diesel": _f(item.get("PRICE_DIESEL") or item.get("diesel")),
        "raw": item,
    }
    stmt = pg_insert(FuelPrice).values(row)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_station_obs",
        set_={
            "gasoline": stmt.excluded.gasoline,
            "premium_gasoline": stmt.excluded.premium_gasoline,
            "diesel": stmt.excluded.diesel,
            "raw": stmt.excluded.raw,
        },
    )
    session.execute(stmt)


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


with DAG(
    dag_id="tripcast_fuel_prices",
    description="여행지 주변 10km 주유소 유가를 하루 3회 갱신",
    schedule="0 6,14,22 * * *",
    start_date=pendulum.datetime(2026, 4, 1, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    tags=["tripcast", "fuel"],
) as dag:
    PythonOperator(task_id="update_fuel_prices", python_callable=update_fuel_prices)
