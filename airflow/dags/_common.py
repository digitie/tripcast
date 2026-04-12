"""Airflow DAG 공통 유틸.

docker-compose 가 backend/app 을 /opt/airflow/lib/tripcast_app 으로 마운트하므로
`tripcast_app.services.*` 모듈을 그대로 import 할 수 있다.
단, 모델/DB 엔진은 Airflow 쪽 DATABASE_URL 을 사용해야 하기 때문에
별도의 SessionLocal 을 만든다.
"""
from __future__ import annotations

import os
import sys

# /opt/airflow/lib 이 PYTHONPATH 에 이미 등록되어 있지만, 직접 실행 시 대비해 한 번 더.
_LIB = "/opt/airflow/lib"
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


DATABASE_URL = os.environ["TRIPCAST_DATABASE_URL"]
DATA_GO_KR_KEY = os.environ.get("DATA_GO_KR_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
