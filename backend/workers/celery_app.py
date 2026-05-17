import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Upstash rediss:// requires ssl_cert_reqs parameter
def _fix_redis_url(url: str) -> str:
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}ssl_cert_reqs=CERT_NONE"
    return url

BROKER_URL = _fix_redis_url(REDIS_URL)
BACKEND_URL = _fix_redis_url(REDIS_URL)

celery_app = Celery(
    "animashorts",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["pipeline.orchestrator"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "pipeline.orchestrator.run_pipeline": {"queue": "video_pipeline"},
    },
    result_expires=86400,
    broker_use_ssl={"ssl_cert_reqs": "CERT_NONE"},
    redis_backend_use_ssl={"ssl_cert_reqs": "CERT_NONE"},
)
