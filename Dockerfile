FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src

RUN groupadd --system aetherflow && useradd --system --gid aetherflow --home-dir /app aetherflow
WORKDIR /app

COPY backend/pyproject.toml /app/backend/
COPY backend/src /app/backend/src
COPY backend/migrations /app/backend/migrations
COPY backend/alembic.ini /app/backend/alembic.ini
RUN pip install --no-cache-dir --disable-pip-version-check /app/backend

USER aetherflow
EXPOSE 8000

CMD ["python", "-m", "aetherflow.runtime.api"]
