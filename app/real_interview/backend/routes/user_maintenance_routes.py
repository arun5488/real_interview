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
@require_auth
def delete_user_route():
    logger.info("[user_maintenance][DELETE /api/users] start")
    body = _parse_json_body()
    if body is None:
        logger.warning("[user_maintenance][DELETE /api/users] invalid JSON body")
        return jsonify({"error": "invalid JSON body"}), 400

    email = g.current_user_email
    password = body.get("password")

    ok, missing = _require_str({"password": password}, "password")
    if not ok:
        logger.warning("[user_maintenance][DELETE /api/users] missing/invalid fields: %s", missing)
        return jsonify({"error": "missing required fields"}), 400

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
