import os
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection

from app.real_interview import logger
from app.real_interview.backend.utils.mongodb import get_mongodb_database

_token_collection_ready = False


def _collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_REVOKED_TOKENS", "revoked_tokens").strip()


def _get_collection() -> Collection:
    global _token_collection_ready
    coll = get_mongodb_database()[_collection_name()]
    if not _token_collection_ready:
        coll.create_index([("jti", 1)], unique=True, name="unique_jti")
        coll.create_index([("exp", 1)], expireAfterSeconds=0, name="ttl_exp")
        _token_collection_ready = True
    return coll


def revoke_token(*, jti: str, exp: datetime) -> None:
    if not jti:
        return
    coll = _get_collection()
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    coll.update_one(
        {"jti": jti},
        {"$set": {"jti": jti, "exp": exp, "revoked_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    logger.info("[token_store] revoked jti=%s", jti)


def is_token_revoked(jti: str) -> bool:
    if not jti:
        return False
    coll = _get_collection()
    return coll.find_one({"jti": jti}, {"_id": 1}) is not None


def revoke_token_from_payload(payload: dict[str, Any]) -> None:
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    if isinstance(exp, (int, float)):
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
    elif hasattr(exp, "timestamp"):
        exp_dt = exp if getattr(exp, "tzinfo", None) else exp.replace(tzinfo=timezone.utc)
    else:
        return
    revoke_token(jti=jti, exp=exp_dt)
