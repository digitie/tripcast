"""시군구 <-> 좌표/격자 유틸.

기상청 동네예보는 (nx, ny) 격자 좌표 체계(LCC)를 사용한다.
여기서는 위/경도 -> (nx, ny) 변환만 정확하게 구현하고,
시군구 -> 위/경도 는 클라이언트가 좌표를 함께 주거나, 사전 매핑 테이블
또는 지오코더를 붙일 수 있도록 stub 을 둔다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# 기상청 Lambert Conformal Conic 파라미터 (공식 문서 기준)
_RE = 6371.00877  # 지구 반경(km)
_GRID = 5.0       # 격자 간격(km)
_SLAT1 = 30.0
_SLAT2 = 60.0
_OLON = 126.0
_OLAT = 38.0
_XO = 43
_YO = 136


@dataclass
class Grid:
    nx: int
    ny: int


def latlon_to_grid(lat: float, lon: float) -> Grid:
    """위/경도(WGS84 근사) -> 기상청 (nx, ny) 격자."""
    degrad = math.pi / 180.0
    re = _RE / _GRID
    slat1 = _SLAT1 * degrad
    slat2 = _SLAT2 * degrad
    olon = _OLON * degrad
    olat = _OLAT * degrad

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * degrad * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * degrad - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + _XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + _YO + 0.5)
    return Grid(nx=nx, ny=ny)


# --- 시군구 -> 대표 좌표 ------------------------------------------------
# 주요 시군구의 대표 위경도. 실제 서비스에서는 data.go.kr 의
# "행정표준코드"+법정동 dataset 또는 네이버/카카오 지오코더를 사용할 것.
# 여기서는 DB 시드 / 개발 편의용 샘플만 제공한다.
SAMPLE_SIGUNGU_COORDS: dict[tuple[str, str], tuple[float, float]] = {
    ("서울특별시", "종로구"): (37.5735, 126.9788),
    ("서울특별시", "강남구"): (37.5172, 127.0473),
    ("부산광역시", "해운대구"): (35.1631, 129.1635),
    ("인천광역시", "중구"): (37.4738, 126.6216),
    ("대구광역시", "중구"): (35.8693, 128.6062),
    ("대전광역시", "서구"): (36.3554, 127.3845),
    ("광주광역시", "동구"): (35.1463, 126.9231),
    ("울산광역시", "남구"): (35.5438, 129.3300),
    ("세종특별자치시", "세종시"): (36.4801, 127.2890),
    ("경기도", "수원시"): (37.2636, 127.0286),
    ("경기도", "용인시"): (37.2411, 127.1776),
    ("강원특별자치도", "강릉시"): (37.7519, 128.8760),
    ("강원특별자치도", "속초시"): (38.2070, 128.5918),
    ("강원특별자치도", "춘천시"): (37.8813, 127.7298),
    ("충청북도", "청주시"): (36.6424, 127.4890),
    ("충청남도", "천안시"): (36.8151, 127.1139),
    ("전라북도", "전주시"): (35.8242, 127.1480),
    ("전북특별자치도", "전주시"): (35.8242, 127.1480),
    ("전라남도", "여수시"): (34.7604, 127.6622),
    ("경상북도", "경주시"): (35.8562, 129.2247),
    ("경상북도", "포항시"): (36.0190, 129.3435),
    ("경상남도", "창원시"): (35.2280, 128.6811),
    ("경상남도", "통영시"): (34.8544, 128.4331),
    ("제주특별자치도", "제주시"): (33.4996, 126.5312),
    ("제주특별자치도", "서귀포시"): (33.2542, 126.5600),
}


def sigungu_to_latlon(sido: str, sigungu: str) -> tuple[float, float] | None:
    return SAMPLE_SIGUNGU_COORDS.get((sido, sigungu))


# --- DB 기반 반경 질의 --------------------------------------------------


def regions_within(db, lat: float, lon: float, radius_m: int) -> list:
    """지정 좌표 반경 내에 포함되거나 교차하는 SigunguRegion 목록을 반환.

    경계 폴리곤 자체와의 거리를 geography 로 계산하므로 여행지를 포함하는
    시군구 + 반경 내로 걸쳐있는 인접 시군구가 모두 포함된다.
    """
    from geoalchemy2.functions import ST_DWithin
    from sqlalchemy import cast, func, select
    from geoalchemy2 import Geography

    from ..models import SigunguRegion

    pt = func.cast(
        func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography
    )
    geom_geo = cast(SigunguRegion.geom, Geography)
    rows = db.scalars(
        select(SigunguRegion)
        .where(SigunguRegion.geom.isnot(None))
        .where(ST_DWithin(geom_geo, pt, radius_m))
        .order_by(func.ST_Distance(geom_geo, pt))
    ).all()
    return list(rows)
