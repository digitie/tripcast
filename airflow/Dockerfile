# multi-arch airflow 이미지 (arm64/amd64)
FROM apache/airflow:2.10.3-python3.12

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-dev libproj-dev build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# /opt/airflow/tripcast_app 는 docker-compose 의 volume mount 로 제공된다.
# DAG 에서는 `from tripcast_app.services...` 와 같이 import 한다.
ENV PYTHONPATH=/opt/airflow:/opt/airflow/lib
