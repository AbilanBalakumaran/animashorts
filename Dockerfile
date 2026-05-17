FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend-builder /app/frontend/out ./static_frontend

RUN mkdir -p /app/outputs /app/assets/music

EXPOSE 7860

CMD ["sh", "-c", "celery -A workers.celery_app worker --loglevel=warning --concurrency=1 -Q video_pipeline & uvicorn main:app --host 0.0.0.0 --port 7860"]
