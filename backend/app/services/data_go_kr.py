"""data.go.kr 공공데이터 API 클라이언트.

본 모듈은 다음 서비스의 얇은 래퍼를 제공한다.

- 기상청_동네예보조회서비스 (VilageFcstInfoService_2.0)
    * getUltraSrtFcst  : 초단기예보 (6시간)
    * getVilageFcst    : 단기예보 (3일)
- 기상청_중기예보조회서비스 (MidFcstInfoService)
    * getMidLandFcst, getMidTa
- 한국도로공사_휴게소정보 (ExpsSvcInfo)
    * getRestArea, getRestAreaWeather
- 한국석유공사_주유소 가격정보 (OilStationInfoService)
    * getLowTop10, 지역/반경 검색 등

주의: 실제 엔드포인트 문자열과 파라미터 이름은 data.go.kr
신청 페이지의 명세를 그대로 사용한다. 인증키(serviceKey) 는 환경변수
DATA_GO_KR_KEY 에서 읽는다. URL 디코딩된 값을 사용할 것.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

import httpx

BASE_WEATHER_SHORT = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
BASE_WEATHER_MID = "https://apis.data.go.kr/1360000/MidFcstInfoService"
BASE_EX_REST_AREA = "https://apis.data.go.kr/B551011/RestAreaService"  # 예시 엔드포인트
BASE_OIL_STATION = "https://apis.data.go.kr/B552015/OilPriceInfoService"  # 예시 엔드포인트


@dataclass
class DataGoKrClient:
    service_key: str
    timeout: float = 20.0

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {"serviceKey": self.service_key, "dataType": "JSON", **params}
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    # ---- 기상청 단기/초단기 ------------------------------------------------
    def get_ultra_short_forecast(self, nx: int, ny: int, base_time: datetime | None = None) -> dict:
        base = _nearest_ultra_base(base_time or datetime.now())
        return self._get(
            f"{BASE_WEATHER_SHORT}/getUltraSrtFcst",
            {
                "numOfRows": 1000,
                "pageNo": 1,
                "base_date": base.strftime("%Y%m%d"),
                "base_time": base.strftime("%H%M"),
                "nx": nx,
                "ny": ny,
            },
        )

    def get_short_forecast(self, nx: int, ny: int, base_time: datetime | None = None) -> dict:
        base = _nearest_short_base(base_time or datetime.now())
        return self._get(
            f"{BASE_WEATHER_SHORT}/getVilageFcst",
            {
                "numOfRows": 1000,
                "pageNo": 1,
                "base_date": base.strftime("%Y%m%d"),
                "base_time": base.strftime("%H%M"),
                "nx": nx,
                "ny": ny,
            },
        )

    # ---- 기상청 중기 -------------------------------------------------------
    def get_mid_land_forecast(self, reg_id: str, tmfc: datetime | None = None) -> dict:
        base = _nearest_mid_base(tmfc or datetime.now())
        return self._get(
            f"{BASE_WEATHER_MID}/getMidLandFcst",
            {
                "numOfRows": 100,
                "pageNo": 1,
                "regId": reg_id,
                "tmFc": base.strftime("%Y%m%d%H%M"),
            },
        )

    def get_mid_ta(self, reg_id: str, tmfc: datetime | None = None) -> dict:
        base = _nearest_mid_base(tmfc or datetime.now())
        return self._get(
            f"{BASE_WEATHER_MID}/getMidTa",
            {
                "numOfRows": 100,
                "pageNo": 1,
                "regId": reg_id,
                "tmFc": base.strftime("%Y%m%d%H%M"),
            },
        )

    # ---- 한국도로공사 휴게소 -----------------------------------------------
    def list_rest_areas(self, page: int = 1, rows: int = 200) -> dict:
        return self._get(
            f"{BASE_EX_REST_AREA}/getRestAreaList",
            {"pageNo": page, "numOfRows": rows},
        )

    def get_rest_area_weather(self, page: int = 1, rows: int = 200) -> dict:
        return self._get(
            f"{BASE_EX_REST_AREA}/getRestAreaWeather",
            {"pageNo": page, "numOfRows": rows},
        )

    # ---- 주유소 유가 -------------------------------------------------------
    def get_fuel_prices_in_radius(
        self, lat: float, lon: float, radius_m: int = 10000, page: int = 1, rows: int = 500
    ) -> dict:
        return self._get(
            f"{BASE_OIL_STATION}/getStationsInRadius",
            {
                "x": lon,
                "y": lat,
                "radius": radius_m,
                "pageNo": page,
                "numOfRows": rows,
            },
        )


# --- helpers: 기상청 base_time 계산 -------------------------------------


_SHORT_BASE_TIMES = [2, 5, 8, 11, 14, 17, 20, 23]


def _nearest_short_base(now: datetime) -> datetime:
    """단기예보: 02, 05, 08, 11, 14, 17, 20, 23시 발표."""
    base = now.replace(minute=0, second=0, microsecond=0)
    # 발표 후 데이터 공급까지 10분 여유
    if now.minute < 10:
        base = base - timedelta(hours=1)
    for h in reversed(_SHORT_BASE_TIMES):
        if base.hour >= h:
            return base.replace(hour=h)
    # 00~01시: 전날 23시
    return (base - timedelta(days=1)).replace(hour=23)


def _nearest_ultra_base(now: datetime) -> datetime:
    """초단기예보: 매시 30분 발표 (30분 이전이면 이전 시각)."""
    base = now.replace(minute=30, second=0, microsecond=0)
    if now.minute < 45:
        base = base - timedelta(hours=1)
    return base


def _nearest_mid_base(now: datetime) -> datetime:
    """중기예보: 06, 18시 발표."""
    base = now.replace(minute=0, second=0, microsecond=0)
    if now.hour >= 18:
        return base.replace(hour=18)
    if now.hour >= 6:
        return base.replace(hour=6)
    return (base - timedelta(days=1)).replace(hour=18)


# --- response parsers ---------------------------------------------------


def iter_forecast_items(response: dict) -> Iterable[dict]:
    """기상청 예보 response -> item 이터레이터."""
    try:
        return response["response"]["body"]["items"]["item"]
    except (KeyError, TypeError):
        return []


# 예보에 나오는 category 코드 매핑
CATEGORY_MAP = {
    "TMP": "temperature",          # 1시간 기온 (단기)
    "T1H": "temperature",          # 기온 (초단기)
    "REH": "humidity",
    "WSD": "wind_speed",
    "PCP": "precipitation",
    "RN1": "precipitation",
    "SKY": "sky",
    "PTY": "pty",
}

SKY_CODE = {"1": "맑음", "3": "구름많음", "4": "흐림"}
PTY_CODE = {
    "0": "없음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
    "5": "빗방울",
    "6": "빗방울눈날림",
    "7": "눈날림",
}
