import os
import ssl
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _broker_url(url: str) -> str:
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}ssl_cert_reqs=CERT_NONE"
    return url


_SSL_OPTS = {"ssl_cert_reqs": ssl.CERT_NONE} if REDIS_URL.startswith("rediss://") else {}

celery_app = Celery(
    "animashorts",
    broker=_broker_url(REDIS_URL),
    backend=_broker_url(REDIS_URL),
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
    broker_connection_retry_on_startup=True,
    **({"broker_use_ssl": _SSL_OPTS, "redis_backend_use_ssl": _SSL_OPTS} if _SSL_OPTS else {}),
)
