FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install ".[serve,api,db]"

COPY alembic.ini ./
COPY migrations ./migrations
COPY reports/test_eval/yolo11s_v1_960_best/metrics.json ./reports/test_eval/yolo11s_v1_960_best/metrics.json

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn weedlab.api.app:create_app --factory --host 0.0.0.0 --port 8000"]