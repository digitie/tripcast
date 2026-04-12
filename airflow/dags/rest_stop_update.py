"""전국 휴게소 정보를 1달에 1번 업데이트.

한국도로공사 '전국 고속도로 휴게소 정보' 를 data.go.kr 에서 받아와 전체 테이블을 upsert.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from _common import DATA_GO_KR_KEY, SessionLocal
from tripcast_app.models import RestStop, RestStopWeather
from tripcast_app.services.data_go_kr import DataGoKrClient


def _iter_pages(client: DataGoKrClient, fn_name: str):
    fn = getattr(client, fn_name)
    page = 1
    while True:
        resp = fn(page=page, rows=200)
        items = _extract_items(resp)
        if not items:
            break
        for it in items:
            yield it
        if len(items) < 200:
            break
        page += 1


def _extract_items(resp: dict) -> list[dict]:
    body = resp.get("response", {}).get("body", {}) or resp.get("body", {})
    items = body.get("items") or {}
    if isinstance(items, dict):
        items = items.get("item", [])
    return items or []


def update_rest_stops() -> None:
    if not DATA_GO_KR_KEY:
        print("DATA_GO_KR_KEY is empty, skip rest stop update")
        return
    client = DataGoKrClient(service_key=DATA_GO_KR_KEY)
    with SessionLocal() as session:
        for item in _iter_pages(client, "list_rest_areas"):
            code = str(item.get("serviceAreaCode") or item.get("unitCode") or item.get("id") or "")
            if not code:
                continue
            lat = _f(item.get("yValue") or item.get("lat"))
            lon = _f(item.get("xValue") or item.get("lon"))
            row = {
                "external_code": code,
                "name": str(item.get("serviceAreaName") or item.get("name") or code),
                "route_name": str(item.get("routeName") or ""),
                "direction": str(item.get("direction") or ""),
                "sido": str(item.get("sido") or ""),
                "sigungu": str(item.get("sigungu") or ""),
                "latitude": lat,
                "longitude": lon,
                "location": from_shape(Point(lon, lat), srid=4326) if lat and lon else None,
                "raw": item,
                "updated_at": datetime.now(tz=timezone.utc),
            }
            stmt = pg_insert(RestStop).values(row)
            stmt = stmt.on_conflict_do_update(
                index_elements=[RestStop.external_code],
                set_={k: stmt.excluded[k] for k in row if k != "external_code"},
            )
            session.execute(stmt)
        session.commit()

        # 날씨 스냅샷도 함께 업데이트 (자주 변하진 않지만 정보 API 에 같이 있으므로)
        for item in _iter_pages(client, "get_rest_area_weather"):
            code = str(item.get("serviceAreaCode") or item.get("unitCode") or "")
            if not code:
                continue
            stop = session.scalar(select(RestStop).where(RestStop.external_code == code))
            if stop is None:
                continue
            w = {
                "rest_stop_id": stop.id,
                "observed_at": datetime.now(tz=timezone.utc),
                "temperature": _f(item.get("tmpr") or item.get("temperature")),
                "humidity": _f(item.get("hd") or item.get("humidity")),
                "wind_speed": _f(item.get("wdSpd") or item.get("wind_speed")),
                "precipitation": _f(item.get("rn") or item.get("precipitation")),
                "sky": str(item.get("weather") or ""),
                "raw": item,
            }
            stmt = pg_insert(RestStopWeather).values(w)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_rest_stop_obs",
                set_={k: stmt.excluded[k] for k in w if k not in ("rest_stop_id", "observed_at")},
            )
            session.execute(stmt)
        session.commit()


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


with DAG(
    dag_id="tripcast_rest_stops_monthly",
    description="전국 휴게소 정보를 1달에 1회 전체 갱신",
    schedule="0 3 1 * *",  # 매월 1일 03:00
    start_date=pendulum.datetime(2026, 4, 1, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    tags=["tripcast", "rest-stops"],
) as dag:
    PythonOperator(task_id="update_rest_stops", python_callable=update_rest_stops)
