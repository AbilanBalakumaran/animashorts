import os
import ssl
import threading
import redis as redis_lib

_lock = threading.Lock()
_redis_client = None


def get_redis() -> redis_lib.Redis:
    global _redis_client
    if _redis_client is None:
        with _lock:
            if _redis_client is None:
                url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                kwargs: dict = {"decode_responses": True}
                if url.startswith("rediss://"):
                    kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
                _redis_client = redis_lib.from_url(url, **kwargs)
    return _redis_client
