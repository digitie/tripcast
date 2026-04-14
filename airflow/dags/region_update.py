"""전국 시군구 행정경계 SHP 를 3달에 1회 다운받아 PostGIS 에 적재.

data.go.kr / 행정안전부 '시군구 행정구역경계' 데이터셋을 사용한다.
다운로드 URL 은 `REGION_SHP_URL` 환경변수(zip 파일의 직링크)로 지정한다.

- pyshp (`shapefile`) 로 SHP 레코드를 읽고,
- pyproj 로 EPSG:5179 / 5186 등 원본 좌표계를 4326(WGS84)으로 변환,
- shapely.geometry.shape 로 MultiPolygon 생성 후 GeoAlchemy2 로 upsert.

데이터셋에서 자주 사용하는 속성 이름:
    SIG_CD     - 시군구 코드 (5자리)
    SIG_KOR_NM - 시군구 한글명 (예: "강원특별자치도 강릉시")
    CTP_KOR_NM - 시도 한글명 (없을 수도 있음)
"""
from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pendulum
import pyproj
import shapefile  # pyshp
from airflow import DAG
from airflow.operators.python import PythonOperator
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Polygon, shape as shp_shape
from shapely.ops import transform as shp_transform
from sqlalchemy.dialects.postgresql import insert as pg_insert

from _common import SessionLocal
from tripcast_app.models import SigunguRegion
from tripcast_app.services.region import latlon_to_grid


REGION_SHP_URL = os.environ.get("REGION_SHP_URL", "")
# 원본 좌표계 (행정안전부 SHP 기본: EPSG:5179). 데이터셋마다 5174/5186 도 있음.
REGION_SHP_SRID = int(os.environ.get("REGION_SHP_SRID", "5179"))


def _split_sido_sigungu(name: str) -> tuple[str, str]:
    """'강원특별자치도 강릉시' -> ('강원특별자치도', '강릉시').

    공백이 없으면 전체를 sigungu 로, sido 는 빈 문자열로 둔다.
    """
    name = (name or "").strip()
    if not name:
        return "", ""
    parts = name.split(None, 1)
    if len(parts) == 1:
        return "", parts[0]
    return parts[0], parts[1]


def _download_zip(url: str) -> bytes:
    with httpx.Client(timeout=180.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


def _find_shp(base_dir: Path) -> Path:
    for p in base_dir.rglob("*.shp"):
        return p
    raise FileNotFoundError(f"no .shp under {base_dir}")


def _record_value(rec: Any, field: str) -> Any:
    try:
        return rec[field]
    except Exception:  # noqa: BLE001
        return None


def _load_shapefile(shp_path: Path) -> list[dict]:
    """SHP -> [{code, sido, sigungu, geom(4326, MultiPolygon)}]."""
    # 소스 좌표계 -> WGS84 변환기.
    src = pyproj.CRS.from_epsg(REGION_SHP_SRID)
    dst = pyproj.CRS.from_epsg(4326)
    project = pyproj.Transformer.from_crs(src, dst, always_xy=True).transform

    reader = shapefile.Reader(str(shp_path), encoding="cp949")
    fields = [f[0] for f in reader.fields[1:]]  # DeletionFlag 제거
    results: list[dict] = []
    for sr in reader.shapeRecords():
        rec = dict(zip(fields, sr.record))
        code = str(
            rec.get("SIG_CD")
            or rec.get("sig_cd")
            or rec.get("ADM_SECT_C")
            or rec.get("CTP_CD")
            or ""
        ).strip()
        raw_name = str(
            rec.get("SIG_KOR_NM")
            or rec.get("sig_kor_nm")
            or rec.get("NAME")
            or ""
        ).strip()
        ctp_name = str(rec.get("CTP_KOR_NM") or "").strip()

        if ctp_name and raw_name and not raw_name.startswith(ctp_name):
            sido, sigungu = ctp_name, raw_name
        else:
            sido, sigungu = _split_sido_sigungu(raw_name)

        if not code:
            code = f"{sido}|{sigungu}"
        if not sigungu:
            continue

        geom = shp_shape(sr.shape.__geo_interface__)
        geom = shp_transform(project, geom)
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        elif not isinstance(geom, MultiPolygon):
            # GeometryCollection 등은 스킵
            continue

        centroid = geom.centroid
        results.append(
            {
                "code": code[:20],
                "sido": sido[:40],
                "sigungu": sigungu[:80],
                "geom": geom,
                "center_lat": centroid.y,
                "center_lon": centroid.x,
            }
        )
    return results


def update_regions() -> None:
    if not REGION_SHP_URL:
        print("REGION_SHP_URL is empty, skip region update")
        return

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        raw = _download_zip(REGION_SHP_URL)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            zf.extractall(td_path)
        shp_path = _find_shp(td_path)
        print(f"loaded shapefile: {shp_path}")
        records = _load_shapefile(shp_path)
        print(f"parsed {len(records)} features")

    with SessionLocal() as session:
        for r in records:
            grid = latlon_to_grid(r["center_lat"], r["center_lon"])
            row = {
                "code": r["code"],
                "sido": r["sido"],
                "sigungu": r["sigungu"],
                "center_lat": r["center_lat"],
                "center_lon": r["center_lon"],
                "center": from_shape(
                    __import__("shapely.geometry", fromlist=["Point"]).Point(
                        r["center_lon"], r["center_lat"]
                    ),
                    srid=4326,
                ),
                "nx": grid.nx,
                "ny": grid.ny,
                "geom": from_shape(r["geom"], srid=4326),
            }
            stmt = pg_insert(SigunguRegion).values(row)
            stmt = stmt.on_conflict_do_update(
                index_elements=[SigunguRegion.code],
                set_={k: stmt.excluded[k] for k in row if k != "code"},
            )
            session.execute(stmt)
        session.commit()


with DAG(
    dag_id="tripcast_region_boundaries_quarterly",
    description="전국 시군구 행정경계 SHP 를 3달에 1회 다운받아 갱신",
    # 1,4,7,10월 1일 02:00 → 사실상 3개월 1회
    schedule="0 2 1 1,4,7,10 *",
    start_date=pendulum.datetime(2026, 4, 1, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    tags=["tripcast", "regions"],
) as dag:
    PythonOperator(task_id="update_regions", python_callable=update_regions)
