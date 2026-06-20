from typing import Any, Dict

from flask import Blueprint, g, jsonify, make_response, request

from app.real_interview import logger
from app.real_interview.backend.auth.cookies import clear_auth_cookie, set_auth_cookie
from app.real_interview.backend.auth.email_utils import normalize_email
from app.real_interview.backend.auth.jwt_auth import (
    create_access_token,
    require_auth,
    revoke_current_token,
)
from app.real_interview.backend.auth.rate_limit import client_ip, rate_limit
from app.real_interview.backend.services.user_maintenance import (
    change_password,
    delete_user,
    login_user,
    sign_up_user,
)
from app.real_interview.backend.services.user_profile_service import get_user_profile, list_profile_interviews
from app.real_interview.backend.services.user_interview_preferences import update_interview_settings

user_maintenance_blueprint = Blueprint("user_maintenance", __name__, url_prefix="/api")


def _parse_json_body() -> Dict[str, Any] | None:
    data = request.get_json(silent=True)
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _attach_auth_cookie(result: Dict[str, Any], *, issue_token: bool = False):
    status_code = int(result.pop("status_code", 200))
    resp = make_response(jsonify(result), status_code)
    if issue_token and status_code in (200, 201):
        user_id = result.get("user_id")
        email = result.get("email")
        if isinstance(user_id, str) and user_id and isinstance(email, str) and email:
            token = create_access_token(user_id=user_id, email=email)
            set_auth_cookie(resp, token)
    return resp


def _require_str(body: Dict[str, Any], *keys: str) -> tuple[bool, Dict[str, str]]:
    missing: Dict[str, str] = {}
    for key in keys:
        value = body.get(key)
        if not isinstance(value, str) or not value.strip():
            missing[key] = "missing or not a non-empty string"
    return (len(missing) == 0), missing


@user_maintenance_blueprint.route("/users/me", methods=["GET"])
@require_auth
def current_user_route():
    return jsonify(
        {
            "user_id": g.current_user_id,
            "email": g.current_user_email,
        }
    ), 200


@user_maintenance_blueprint.route("/users/profile", methods=["GET"])
@require_auth
def user_profile_route():
    logger.info("[user_maintenance][GET /api/users/profile] user_id=%s", g.current_user_id)
    result = get_user_profile(customer_id=g.current_user_id, email=g.current_user_email)
    status_code = int(result.pop("status_code", 200))
    return jsonify(result), status_code


@user_maintenance_blueprint.route("/users/profile/interviews", methods=["GET"])
@require_auth
def user_profile_interviews_route():
    kind = (request.args.get("status") or request.args.get("kind") or "").strip().lower()
    if kind not in ("completed", "paused"):
        return jsonify({"error": "status must be completed or paused"}), 400
    logger.info(
        "[user_maintenance][GET /api/users/profile/interviews] user_id=%s status=%s",
        g.current_user_id,
        kind,
    )
    try:
        result = list_profile_interviews(customer_id=g.current_user_id, kind=kind)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    status_code = int(result.pop("status_code", 200))
    return jsonify(result), status_code


@user_maintenance_blueprint.route("/users/profile/interview-settings", methods=["PUT"])
@require_auth
def user_profile_interview_settings_route():
    logger.info(
        "[user_maintenance][PUT /api/users/profile/interview-settings] user_id=%s",
        g.current_user_id,
    )
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    has_max = "max_questions_per_interviewer" in body
    has_ideal = "ideal_answer_report_enabled" in body
    if not has_max and not has_ideal:
        return jsonify(
            {"error": "provide max_questions_per_interviewer and/or ideal_answer_report_enabled"}
        ), 400

    max_value: int | None | object = ...
    if has_max:
        raw = body.get("max_questions_per_interviewer")
        if raw is None:
            max_value = None
        else:
            try:
                max_value = int(raw)
            except (TypeError, ValueError):
                return jsonify({"error": "max_questions_per_interviewer must be an integer or null"}), 400

    ideal_enabled: bool | None = None
    if has_ideal:
        raw_ideal = body.get("ideal_answer_report_enabled")
        if not isinstance(raw_ideal, bool):
            return jsonify({"error": "ideal_answer_report_enabled must be a boolean"}), 400
        ideal_enabled = raw_ideal

    result = update_interview_settings(
        g.current_user_id,
        max_questions_per_interviewer=max_value,
        ideal_answer_report_enabled=ideal_enabled,
    )
    status_code = int(result.pop("status_code", 200))
    return jsonify(result), status_code


@user_maintenance_blueprint.route("/users/logout", methods=["POST"])
def logout_user_route():
    logger.info("[user_maintenance][POST /api/users/logout]")
    revoke_current_token()
    resp = make_response(jsonify({"message": "signed out successfully"}), 200)
    clear_auth_cookie(resp)
    return resp


@user_maintenance_blueprint.route("/users", methods=["POST"])
@rate_limit(scope="signup_ip", max_attempts=5, window_seconds=3600, key=client_ip)
def sign_up_user_route():
    logger.info("[user_maintenance][POST /api/users] start")
    body = _parse_json_body()
    if body is None:
        logger.warning("[user_maintenance][POST /api/users] invalid JSON body")
        return jsonify({"error": "invalid JSON body"}), 400

    email = body.get("email") or body.get("emailid")
    password = body.get("password")
    confirm_password = body.get("confirm_password") or body.get("confirmPassword")

    ok, missing = _require_str(
        {"email": email, "password": password, "confirm_password": confirm_password},
        "email",
        "password",
        "confirm_password",
    )
    if not ok:
        logger.warning("[user_maintenance][POST /api/users] missing/invalid fields: %s", missing)
        return jsonify({"error": "missing required fields"}), 400

    logger.info("[user_maintenance][POST /api/users] invoking service")
    result = sign_up_user(email=email, password=password, confirm_password=confirm_password)  # type: ignore[arg-type]
    logger.info("[user_maintenance][POST /api/users] finished with status_code=%s", result.get("status_code"))
    return _attach_auth_cookie(result, issue_token=True)


@user_maintenance_blueprint.route("/users/login", methods=["POST"])
@rate_limit(scope="login_ip", max_attempts=10, window_seconds=60, key=client_ip)
def login_user_route():
    logger.info("[user_maintenance][POST /api/users/login] start")
    body = _parse_json_body()
    if body is None:
        logger.warning("[user_maintenance][POST /api/users/login] invalid JSON body")
        return jsonify({"error": "invalid JSON body"}), 400

    email = body.get("email") or body.get("emailid")
    password = body.get("password")

    ok, missing = _require_str({"email": email, "password": password}, "email", "password")
    if not ok:
        logger.warning(
            "[user_maintenance][POST /api/users/login] missing/invalid fields: %s",
            missing,
        )
        return jsonify({"error": "missing required fields"}), 400

    from app.real_interview.backend.auth.rate_limit import enforce_rate_limit

    email_key = normalize_email(email if isinstance(email, str) else "")
    if email_key:
        allowed, retry_after = enforce_rate_limit(
            scope="login_email",
            key=email_key,
            max_attempts=5,
            window_seconds=900,
        )
        if not allowed:
            return (
                jsonify({"error": "too many requests", "retry_after_seconds": retry_after}),
                429,
            )

    logger.info("[user_maintenance][POST /api/users/login] invoking service")
    result = login_user(email=email, password=password)  # type: ignore[arg-type]
    logger.info(
        "[user_maintenance][POST /api/users/login] finished with status_code=%s",
        result.get("status_code"),
    )
    return _attach_auth_cookie(result, issue_token=True)


@user_maintenance_blueprint.route("/users/password", methods=["PUT"])
@require_auth
@rate_limit(scope="change_password_user", max_attempts=5, window_seconds=3600, key=lambda: g.current_user_id)
def change_password_route():
    logger.info("[user_maintenance][PUT /api/users/password] start")
    body = _parse_json_body()
    if body is None:
        logger.warning("[user_maintenance][PUT /api/users/password] invalid JSON body")
        return jsonify({"error": "invalid JSON body"}), 400

    email = g.current_user_email
    current_password = body.get("current_password") or body.get("currentPassword")
    new_password = body.get("new_password") or body.get("newPassword")
    confirm_new_password = body.get("confirm_new_password") or body.get("confirmNewPassword")

    ok, missing = _require_str(
        {
            "current_password": current_password,
            "new_password": new_password,
            "confirm_new_password": confirm_new_password,
        },
        "current_password",
        "new_password",
        "confirm_new_password",
    )
    if not ok:
        logger.warning(
            "[user_maintenance][PUT /api/users/password] missing/invalid fields: %s",
            missing,
        )
        return jsonify({"error": "missing required fields"}), 400

    logger.info("[user_maintenance][PUT /api/users/password] invoking service")
    result = change_password(  # type: ignore[arg-type]
        email=email,
        current_password=current_password,
        new_password=new_password,
        confirm_new_password=confirm_new_password,
    )
    logger.info(
        "[user_maintenance][PUT /api/users/password] finished with status_code=%s",
        result.get("status_code"),
    )
    status_code = int(result.pop("status_code", 200))
    if status_code == 200:
        revoke_current_token()
        resp = make_response(jsonify(result), status_code)
        clear_auth_cookie(resp)
        return resp
    return jsonify(result), status_code


@user_maintenance_blueprint.route("/users", methods=["DELETE"])
@rate_limit(scope="delete_account_ip", max_attempts=5, window_seconds=3600, key=client_ip)
def delete_user_route():
    logger.info("[user_maintenance][DELETE /api/users] start")
    body = _parse_json_body()
    if body is None:
        logger.warning("[user_maintenance][DELETE /api/users] invalid JSON body")
        return jsonify({"error": "invalid JSON body"}), 400

    email = body.get("email") or body.get("emailid")
    password = body.get("password")

    ok, missing = _require_str({"email": email, "password": password}, "email", "password")
    if not ok:
        logger.warning("[user_maintenance][DELETE /api/users] missing/invalid fields: %s", missing)
        return jsonify({"error": "missing required fields"}), 400

    from app.real_interview.backend.auth.rate_limit import enforce_rate_limit

    email_key = normalize_email(email if isinstance(email, str) else "")
    if email_key:
        allowed, retry_after = enforce_rate_limit(
            scope="delete_account_email",
            key=email_key,
            max_attempts=5,
            window_seconds=900,
        )
        if not allowed:
            return (
                jsonify({"error": "too many requests", "retry_after_seconds": retry_after}),
                429,
            )

    logger.info("[user_maintenance][DELETE /api/users] invoking service")
    result = delete_user(  # type: ignore[arg-type]
        email=email,
        password=password,
    )
    logger.info("[user_maintenance][DELETE /api/users] finished with status_code=%s", result.get("status_code"))
    status_code = int(result.pop("status_code", 200))
    if status_code == 200:
        revoke_current_token()
        resp = make_response(jsonify(result), status_code)
        clear_auth_cookie(resp)
        return resp
    return jsonify(result), status_code
