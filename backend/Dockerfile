FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/outputs /app/assets/music

EXPOSE 8000

CMD ["sh", "-c", "celery -A workers.celery_app worker --loglevel=info --concurrency=1 -Q video_pipeline & uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
