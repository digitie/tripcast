"""저장된 여행의 (nx,ny) 격자별로 기상청 예보를 30분마다 갱신.

- 여행 1일 전 ~ 여행 중: 초단기 예보 (시간 단위)
- 그 외: 단기 예보 + 중기 예보
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from _common import DATA_GO_KR_KEY, SessionLocal
from tripcast_app.models import Trip, TripPlace, WeatherForecast
from tripcast_app.services.data_go_kr import (
    CATEGORY_MAP,
    DataGoKrClient,
    PTY_CODE,
    SKY_CODE,
    iter_forecast_items,
)


def _active_grid_places(session) -> Iterable[tuple[int, int, bool]]:
    """(nx, ny, need_ultra)  dedup."""
    today = date.today()
    rows = session.scalars(
        select(Trip).where(Trip.end_date >= today).where(Trip.telegram_enabled.is_(True))
    ).all()
    seen: dict[tuple[int, int], bool] = {}
    for t in rows:
        window_start = t.start_date - timedelta(days=t.notify_lead_days)
        if today < window_start:
            continue
        ultra_needed = (t.start_date - today).days <= 1 or (t.start_date <= today <= t.end_date)
        for p in t.places:
            if p.nx is None or p.ny is None:
                continue
            k = (p.nx, p.ny)
            seen[k] = seen.get(k, False) or ultra_needed
    for (nx, ny), need in seen.items():
        yield nx, ny, need


def _parse_items_to_forecasts(nx: int, ny: int, kind: str, items: list[dict]) -> list[dict]:
    """기상청 item 리스트 -> (fcstDate+fcstTime) 별로 묶어 WeatherForecast row 로."""
    grouped: dict[str, dict] = {}
    for it in items:
        key = f"{it.get('fcstDate')}{it.get('fcstTime')}"
        row = grouped.setdefault(
            key,
            {
                "nx": nx,
                "ny": ny,
                "kind": kind,
                "base_at": datetime.strptime(
                    f"{it.get('baseDate')}{it.get('baseTime')}", "%Y%m%d%H%M"
                ).replace(tzinfo=timezone.utc),
                "forecast_at": datetime.strptime(
                    f"{it.get('fcstDate')}{it.get('fcstTime')}", "%Y%m%d%H%M"
                ).replace(tzinfo=timezone.utc),
                "raw": {},
            },
        )
        cat = it.get("category")
        val = it.get("fcstValue")
        row["raw"][cat] = val
        field = CATEGORY_MAP.get(cat)
        if field == "temperature":
            try:
                row["temperature"] = float(val)
            except (TypeError, ValueError):
                pass
        elif field == "humidity":
            try:
                row["humidity"] = float(val)
            except (TypeError, ValueError):
                pass
        elif field == "wind_speed":
            try:
                row["wind_speed"] = float(val)
            except (TypeError, ValueError):
                pass
        elif field == "precipitation":
            row["precipitation"] = _parse_pcp(val)
        elif field == "sky":
            row["sky"] = SKY_CODE.get(str(val), str(val))
        elif field == "pty":
            row["pty"] = PTY_CODE.get(str(val), str(val))
    return list(grouped.values())


def _parse_pcp(v: str | None) -> float | None:
    if v is None or v in ("강수없음", "-", "0", "0.0"):
        return 0.0
    try:
        return float(str(v).replace("mm", "").strip())
    except ValueError:
        return None


def update_weather() -> None:
    if not DATA_GO_KR_KEY:
        print("DATA_GO_KR_KEY is empty, skipping weather fetch")
        return
    client = DataGoKrClient(service_key=DATA_GO_KR_KEY)
    with SessionLocal() as session:
        for nx, ny, need_ultra in _active_grid_places(session):
            # 단기 예보는 항상 업데이트
            try:
                resp = client.get_short_forecast(nx, ny)
                items = list(iter_forecast_items(resp))
                rows = _parse_items_to_forecasts(nx, ny, "short", items)
                _upsert_forecasts(session, rows)
            except Exception as e:  # noqa: BLE001
                print(f"short forecast failed for {nx},{ny}: {e}")

            if need_ultra:
                try:
                    resp = client.get_ultra_short_forecast(nx, ny)
                    items = list(iter_forecast_items(resp))
                    rows = _parse_items_to_forecasts(nx, ny, "ultra", items)
                    _upsert_forecasts(session, rows)
                except Exception as e:  # noqa: BLE001
                    print(f"ultra forecast failed for {nx},{ny}: {e}")
        session.commit()


def _upsert_forecasts(session, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = pg_insert(WeatherForecast).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_fcst_grid_time",
        set_={
            "base_at": stmt.excluded.base_at,
            "temperature": stmt.excluded.temperature,
            "sky": stmt.excluded.sky,
            "pty": stmt.excluded.pty,
            "precipitation": stmt.excluded.precipitation,
            "humidity": stmt.excluded.humidity,
            "wind_speed": stmt.excluded.wind_speed,
            "raw": stmt.excluded.raw,
            "fetched_at": datetime.now(tz=timezone.utc),
        },
    )
    session.execute(stmt)


with DAG(
    dag_id="tripcast_weather_30min",
    description="저장된 여행지 (nx,ny) 에 대한 기상청 단기/초단기 예보 갱신",
    schedule="*/30 * * * *",
    start_date=pendulum.datetime(2026, 4, 1, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    tags=["tripcast", "weather"],
) as dag:
    PythonOperator(task_id="update_weather", python_callable=update_weather)
