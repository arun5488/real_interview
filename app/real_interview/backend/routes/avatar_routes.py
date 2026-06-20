from typing import Any, Dict, List

from flask import Blueprint, g, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.auth.jwt_auth import require_auth
from app.real_interview.backend.auth.rate_limit import client_ip, rate_limit
from app.real_interview.backend.services.avatar_discuss_service import (
    discuss_with_avatar,
    get_avatar_discuss_context,
)

avatar_blueprint = Blueprint("avatar", __name__, url_prefix="/api/avatar")


def _parse_json_body() -> Dict[str, Any] | None:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return None
    return data


def _normalize_history(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for item in raw[-20:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        out.append({"role": role, "content": text[:4000]})
    return out


@avatar_blueprint.route("/discuss/context", methods=["GET"])
@require_auth
def avatar_discuss_context_route():
    logger.info("[avatar][GET /api/avatar/discuss/context] user_id=%s", g.current_user_id)
    result = get_avatar_discuss_context(customer_id=g.current_user_id)
    status_code = int(result.pop("status_code", 200))
    return jsonify(result), status_code


@avatar_blueprint.route("/discuss", methods=["POST"])
@require_auth
@rate_limit(scope="avatar_discuss_user", max_attempts=30, window_seconds=3600, key=lambda: g.current_user_id)
@rate_limit(scope="avatar_discuss_ip", max_attempts=60, window_seconds=3600, key=client_ip)
def avatar_discuss_route():
    logger.info("[avatar][POST /api/avatar/discuss] user_id=%s", g.current_user_id)
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "message is required"}), 400

    resume_id = body.get("resume_id")
    if resume_id is not None and not isinstance(resume_id, str):
        return jsonify({"error": "resume_id must be a string"}), 400

    history = _normalize_history(body.get("history"))
    result = discuss_with_avatar(
        customer_id=g.current_user_id,
        message=message.strip(),
        history=history,
        resume_id=resume_id.strip() if isinstance(resume_id, str) else None,
    )
    status_code = int(result.pop("status_code", 200))
    return jsonify(result), status_code
