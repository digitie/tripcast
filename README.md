# tripcast

국내 여행 알림 앱.  저장된 여행 정보를 기반으로 기상청 단기/초단기/중기 예보,
전국 고속도로 휴게소 날씨, 여행지 반경 10km 평균 유가를 텔레그램으로 전송한다.

## 스택
- 프론트: Vite + React 18 + TypeScript
- 백엔드: FastAPI + SQLAlchemy 2.0 + GeoAlchemy2 + Shapely
- DB: PostgreSQL 16 + PostGIS 3
- 스케줄러: Apache Airflow 2.10 (LocalExecutor)
- 컨테이너: Docker / docker-compose, arm64(odroid m1s) & amd64(WSL2 Ubuntu 24.04) 동작

## 디렉토리
```
tripcast/
├── docker-compose.yml         # 전체 서비스 오케스트레이션
├── db/init.sql                # postgis/pgcrypto 확장 초기화
├── backend/                   # FastAPI 앱
│   ├── app/
│   │   ├── main.py            # FastAPI 진입점
│   │   ├── models.py          # SQLAlchemy 2.0 + GeoAlchemy 모델
│   │   ├── schemas.py         # Pydantic v2 스키마
│   │   ├── routers/           # /auth /users /trips
│   │   └── services/          # data_go_kr, telegram, report, region
│   └── alembic/               # 스키마 마이그레이션
├── frontend/                  # Vite + React SPA
│   └── src/pages              # Login/Register/Profile/Trips/TripEditor
└── airflow/
    ├── Dockerfile
    └── dags/
        ├── weather_update.py        # 30분마다 여행지 예보 갱신
        ├── fuel_price_update.py     # 하루 3회 유가 갱신 (06/14/22)
        ├── rest_stop_update.py      # 월 1회 전국 휴게소 갱신
        └── travel_notify.py         # 30분마다 알림 전송
```

## 실행

```bash
cp .env.example .env
# .env 에 DATA_GO_KR_KEY, TELEGRAM_BOT_TOKEN, JWT_SECRET 등을 채운 뒤
docker compose build
docker compose up -d
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000  (OpenAPI: /docs)
- Airflow: http://localhost:8080  (기본 admin/admin, `.env` 에서 변경)
- Postgres: localhost:5432 (tripcast/tripcast/tripcast)

## 기능 요약

1. **사용자**: 이메일을 아이디로 가입/로그인. 회원가입 시 텔레그램 chat_id 와
   알림 사용 여부를 기본값으로 등록한다. 내 정보 페이지에서 비밀번호/텔레그램 값을 변경 가능.
2. **여행 계획**: 제목/기간과 "날짜별 장소"(시군구 단위) 를 여러 개 입력. 각 여행마다
   기본값을 덮어쓸 수 있는 텔레그램 chat_id, 알림 리드타임(N일 전) 지정 가능.
3. **좌표 변환**: 시군구 → 대표 위/경도 (샘플 매핑 + 후일 지오코더 연동).
   위경도 → 기상청 동네예보 격자 (nx, ny) 변환은 LCC 공식 구현.
4. **예보**: Airflow 가 30분마다 여행지 격자에 대해 단기예보를 갱신하고,
   여행 1일 전부터는 초단기예보(시간단위)를 추가로 가져온다. 중기예보는 regId 기반.
5. **휴게소**: 월 1회 전국 휴게소 메타/날씨를 전체 갱신. 여행지 근처 휴게소의
   최근 날씨를 리포트에 함께 표시 (PostGIS `ST_DWithin`).
6. **유가**: 하루 3번(06/14/22시) 여행지 반경 10km 내 주유소 가격을 수집,
   휘발유/경유/고급유 평균을 리포트에 포함.
7. **알림**: 여행 시작 N일 전~여행 종료일까지 30분마다 `tripcast_travel_notify`
   DAG 가 실행되어 조건에 맞는 사용자에게 텔레그램으로 리포트를 전송하고
   `notification_logs` 에 기록한다.

## 주의
`backend/app/services/data_go_kr.py` 의 엔드포인트는 data.go.kr 각 서비스의
정식 URL / 파라미터 명세를 그대로 사용한다. 인증키 신청(URL Decoded 키 사용)
후 `DATA_GO_KR_KEY` 에 설정하면 DAG 들이 바로 동작한다.  응답 JSON 의
필드명은 서비스마다 다르므로 `fuel_price_update.py` / `rest_stop_update.py`
의 `item.get(...)` 키는 실제 응답에 맞춰 조정이 필요할 수 있다.
