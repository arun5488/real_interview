import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional

import jwt
from flask import g, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.auth.cookies import get_cookie_token
from app.real_interview.backend.auth.token_store import is_token_revoked, revoke_token_from_payload

_DEV_INSECURE_SECRET = "dev-insecure-change-me-in-production"
_MIN_SECRET_LEN = 32
_PLACEHOLDER_SECRETS = frozenset(
    {
        "change-me-to-a-long-random-string",
        "change-me",
        _DEV_INSECURE_SECRET,
    }
)


def _allow_insecure_dev() -> bool:
    return os.getenv("ALLOW_INSECURE_JWT_DEV", "").strip().lower() in ("1", "true", "yes")


def validate_jwt_config() -> None:
    if _allow_insecure_dev():
        secret = os.getenv("JWT_SECRET_KEY", "").strip() or os.getenv("FLASK_SECRET_KEY", "").strip()
        if not secret:
            logger.warning(
                "[jwt_auth] ALLOW_INSECURE_JWT_DEV is set and JWT_SECRET_KEY is empty; "
                "using insecure dev secret — never use this in production"
            )
        return

    secret = os.getenv("JWT_SECRET_KEY", "").strip() or os.getenv("FLASK_SECRET_KEY", "").strip()
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY is required. Add a random secret (32+ chars) to .env or hosting env vars. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if len(secret) < _MIN_SECRET_LEN:
        raise RuntimeError(
            f"JWT_SECRET_KEY must be at least {_MIN_SECRET_LEN} characters for production use."
        )
    if secret in _PLACEHOLDER_SECRETS:
        raise RuntimeError(
            "JWT_SECRET_KEY is still a placeholder. Generate a secure random value before deploying."
        )


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "").strip() or os.getenv("FLASK_SECRET_KEY", "").strip()
    if secret:
        return secret
    if _allow_insecure_dev():
        logger.warning("[jwt_auth] using insecure dev JWT secret")
        return _DEV_INSECURE_SECRET
    raise RuntimeError("JWT_SECRET_KEY is not configured")


def _jwt_expire_hours() -> int:
    raw = os.getenv("JWT_EXPIRE_HOURS", "24").strip() or "24"
    try:
        return max(1, int(raw))
    except ValueError:
        return 24


def jwt_expire_seconds() -> int:
    return _jwt_expire_hours() * 3600


def create_access_token(*, user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(hours=_jwt_expire_hours()),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm="HS256")
    return token if isinstance(token, str) else token.decode("utf-8")


def decode_access_token(token: str) -> Dict[str, Any]:
    payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise jwt.InvalidTokenError("token revoked")
    user_id = payload.get("sub")
    if not user_id or not isinstance(user_id, str):
        raise jwt.InvalidTokenError("token missing subject")
    return {
        "user_id": user_id,
        "email": payload.get("email") or "",
        "jti": jti or "",
        "exp": payload.get("exp"),
    }


def get_access_token() -> Optional[str]:
    cookie_token = get_cookie_token()
    if cookie_token:
        return cookie_token
    header = request.headers.get("Authorization", "")
    if isinstance(header, str) and header.startswith("Bearer "):
        token = header[7:].strip()
        return token or None
    return None


def get_current_user() -> Optional[Dict[str, str]]:
    token = get_access_token()
    if not token:
        return None
    try:
        return decode_access_token(token)
    except jwt.ExpiredSignatureError:
        logger.info("[jwt_auth] expired token")
        return None
    except jwt.InvalidTokenError:
        logger.info("[jwt_auth] invalid token")
        return None


def require_auth(view: Callable) -> Callable:
    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        user = get_current_user()
        if not user:
            return jsonify({"error": "authentication required"}), 401
        g.current_user_id = user["user_id"]
        g.current_user_email = user.get("email") or ""
        return view(*args, **kwargs)

    return wrapper


def revoke_current_token() -> None:
    token = get_access_token()
    if not token:
        return
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
        revoke_token_from_payload(payload)
    except jwt.InvalidTokenError:
        logger.info("[jwt_auth] could not revoke token")


def interview_session_owned_by(session_id: str, user_id: str) -> bool:
    if not session_id or not user_id:
        return False
    prefix = f"{user_id}:"
    if session_id.startswith(prefix):
        return True
    from app.real_interview.backend.services import interview_record as interview_db

    record = interview_db.get_interview_by_session(session_id)
    if not record:
        return False
    return (record.get("candidate_id") or "") == user_id
