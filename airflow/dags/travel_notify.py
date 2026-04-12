"""여행 알림 전송 DAG.

- 30분 주기로 알림 대상 여행을 찾아 텔레그램 메시지를 발송.
- build_trip_message / iter_trips_needing_notification 는 backend 와 공유.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

from _common import SessionLocal, TELEGRAM_BOT_TOKEN
from tripcast_app.services.report import send_trip_reports
from tripcast_app.services.telegram import TelegramClient


def run_notifications() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN empty, skip notifications")
        return
    telegram = TelegramClient(token=TELEGRAM_BOT_TOKEN)
    with SessionLocal() as session:
        sent = send_trip_reports(session, telegram, now=datetime.now(timezone.utc))
        print(f"sent {sent} notifications")


with DAG(
    dag_id="tripcast_travel_notify",
    description="여행 시작 N일 전부터 텔레그램으로 날씨/유가 리포트 발송",
    schedule="*/30 * * * *",
    start_date=pendulum.datetime(2026, 4, 1, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    tags=["tripcast", "notify"],
) as dag:
    PythonOperator(task_id="send_notifications", python_callable=run_notifications)
