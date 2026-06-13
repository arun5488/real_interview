import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Union

from flask import jsonify, request

from app.real_interview import logger
from app.real_interview.backend.utils.mongodb import get_mongodb_database

KeyFunc = Union[str, Callable[[], str]]


def client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if isinstance(forwarded, str) and forwarded.strip():
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_RATE_LIMITS", "rate_limits").strip()


def _ensure_utc_aware(value: datetime | None) -> datetime | None:
    """MongoDB returns naive UTC datetimes; normalize before comparing with aware `now`."""
    if value is None or not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> tuple[bool, int]:
    coll = get_mongodb_database()[_collection_name()]
    now = datetime.now(timezone.utc)
    doc = coll.find_one({"_id": key})
    if not doc:
        coll.replace_one(
            {"_id": key},
            {"_id": key, "count": 1, "reset_at": now + timedelta(seconds=window_seconds)},
            upsert=True,
        )
        return True, 0

    reset_at = _ensure_utc_aware(doc.get("reset_at"))
    if reset_at is None or reset_at < now:
        coll.replace_one(
            {"_id": key},
            {"_id": key, "count": 1, "reset_at": now + timedelta(seconds=window_seconds)},
            upsert=True,
        )
        return True, 0

    count = int(doc.get("count") or 0)
    if count >= max_attempts:
        retry_after = max(1, int((reset_at - now).total_seconds()))
        return False, retry_after

    coll.update_one({"_id": key}, {"$inc": {"count": 1}})
    return True, 0


def enforce_rate_limit(*, scope: str, key: str, max_attempts: int, window_seconds: int) -> tuple[bool, int]:
    return _check_rate_limit(f"{scope}:{key}", max_attempts, window_seconds)


def rate_limit(*, scope: str, max_attempts: int, window_seconds: int, key: KeyFunc):
    """MongoDB-backed rate limiter (shared across workers)."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapper(*args: Any, **kwargs: Any):
            key_value = key() if callable(key) else key
            limit_key = f"{scope}:{key_value}"
            allowed, retry_after = _check_rate_limit(limit_key, max_attempts, window_seconds)
            if not allowed:
                logger.warning("[rate_limit] blocked scope=%s key=%s", scope, key_value)
                return (
                    jsonify(
                        {
                            "error": "too many requests",
                            "retry_after_seconds": retry_after,
                        }
                    ),
                    429,
                )
            return view(*args, **kwargs)

        return wrapper

    return decorator
