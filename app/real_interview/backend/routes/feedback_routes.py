from typing import Any, Dict

from flask import Blueprint, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.auth.jwt_auth import get_current_user
from app.real_interview.backend.auth.rate_limit import client_ip, rate_limit
from app.real_interview.backend.services.email_service import is_smtp_configured, send_feedback_email

feedback_blueprint = Blueprint("feedback", __name__, url_prefix="/api/feedback")

_MAX_MESSAGE_LEN = 5000
_MIN_MESSAGE_LEN = 10
_ALLOWED_CATEGORIES = {"general", "bug", "feature", "usability", "other"}


def _parse_json_body() -> Dict[str, Any] | None:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return None
    return data


@feedback_blueprint.route("", methods=["POST"])
@rate_limit(scope="feedback_ip", max_attempts=5, window_seconds=3600, key=client_ip)
def submit_feedback_route():
    logger.info("[feedback][POST /api/feedback] start")
    if not is_smtp_configured():
        logger.warning("[feedback] SMTP not configured")
        return jsonify({"error": "feedback is temporarily unavailable"}), 503

    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    message = body.get("message")
    if not isinstance(message, str):
        return jsonify({"error": "message is required"}), 400
    message = message.strip()
    if len(message) < _MIN_MESSAGE_LEN:
        return jsonify({"error": f"message must be at least {_MIN_MESSAGE_LEN} characters"}), 400
    if len(message) > _MAX_MESSAGE_LEN:
        return jsonify({"error": f"message must be at most {_MAX_MESSAGE_LEN} characters"}), 400

    contact_email = ""
    raw_email = body.get("contact_email") or body.get("email")
    if isinstance(raw_email, str) and raw_email.strip():
        contact_email = raw_email.strip().lower()

    category = "general"
    raw_category = body.get("category")
    if isinstance(raw_category, str) and raw_category.strip():
        normalized = raw_category.strip().lower()
        category = normalized if normalized in _ALLOWED_CATEGORIES else "general"

    user = get_current_user()
    user_id = user.get("user_id") if user else None
    user_email = user.get("email") if user else None
    if not contact_email and user_email:
        contact_email = user_email

    ok, err = send_feedback_email(
        message=message,
        contact_email=contact_email,
        category=category,
        user_id=user_id,
        user_email=user_email,
        client_ip=client_ip(),
    )
    if not ok:
        return jsonify({"error": err or "failed to send feedback"}), 500

    return jsonify({"message": "thank you — your feedback was sent"}), 200
