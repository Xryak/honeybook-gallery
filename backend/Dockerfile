# Honeybook backend — FastAPI + SQLite, single-stage slim image.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HONEYBOOK_DB_URL=sqlite:////data/app.db

WORKDIR /app

# curl: healthcheck.  fonts-dejavu-core: Pillow stamps the photo id onto each
# generated seed JPEG and needs a real TTF (the macOS Arial path won't exist).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (layer caching), then the app.
COPY pyproject.toml ./
COPY app ./app
COPY seed ./seed
RUN pip install -e .

# SQLite lives on a mounted volume so favorites survive `compose down && up`.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
