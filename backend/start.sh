#!/bin/bash
# Lance le worker Celery en arrière-plan puis démarre le serveur API
celery -A workers.celery_app worker --loglevel=info --concurrency=1 -Q video_pipeline &
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
