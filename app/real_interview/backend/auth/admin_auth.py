import os
from functools import wraps
from typing import Any, Callable, Set

from flask import g, jsonify

from app.real_interview import logger
from app.real_interview.backend.auth.email_utils import normalize_email
from app.real_interview.backend.auth.jwt_auth import require_auth


def admin_emails() -> Set[str]:
    raw = os.getenv("ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {normalize_email(part.strip()) for part in raw.split(",") if part.strip()}


def is_admin_email(email: str) -> bool:
    normalized = normalize_email(email or "")
    if not normalized:
        return False
    allowed = admin_emails()
    if not allowed:
        logger.warning("[admin_auth] ADMIN_EMAILS is not configured")
        return False
    return normalized in allowed


def require_admin(view: Callable) -> Callable:
    """JWT auth + email must appear in ADMIN_EMAILS."""

    @require_auth
    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        if not is_admin_email(g.current_user_email or ""):
            logger.warning("[admin_auth] forbidden user_id=%s", g.current_user_id)
            return jsonify({"error": "admin access required"}), 403
        return view(*args, **kwargs)

    return wrapper
