from typing import Any, Dict

from flask import Blueprint, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.services.user_maintenance import (
    change_password,
    delete_user,
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


def _service_result_to_response(result: Dict[str, Any]):
    status_code = int(result.pop("status_code", 200))
    return jsonify(result), status_code


def _require_str(body: Dict[str, Any], *keys: str) -> tuple[bool, Dict[str, str]]:
    missing: Dict[str, str] = {}
    for key in keys:
        value = body.get(key)
        if not isinstance(value, str) or not value.strip():
            missing[key] = "missing or not a non-empty string"
    return (len(missing) == 0), missing


@user_maintenance_blueprint.route("/users", methods=["POST"])
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
    return _service_result_to_response(result)


@user_maintenance_blueprint.route("/users/password", methods=["PUT"])
def change_password_route():
    logger.info("[user_maintenance][PUT /api/users/password] start")
    body = _parse_json_body()
    if body is None:
        logger.warning("[user_maintenance][PUT /api/users/password] invalid JSON body")
        return jsonify({"error": "invalid JSON body"}), 400

    email = body.get("email") or body.get("emailid")
    new_password = body.get("new_password") or body.get("newPassword")
    confirm_new_password = body.get("confirm_new_password") or body.get("confirmNewPassword")

    ok, missing = _require_str(
        {
            "email": email,
            "new_password": new_password,
            "confirm_new_password": confirm_new_password,
        },
        "email",
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
        new_password=new_password,
        confirm_new_password=confirm_new_password,
    )
    logger.info(
        "[user_maintenance][PUT /api/users/password] finished with status_code=%s",
        result.get("status_code"),
    )
    return _service_result_to_response(result)


@user_maintenance_blueprint.route("/users", methods=["DELETE"])
def delete_user_route():
    logger.info("[user_maintenance][DELETE /api/users] start")
    body = _parse_json_body()
    if body is None:
        logger.warning("[user_maintenance][DELETE /api/users] invalid JSON body")
        return jsonify({"error": "invalid JSON body"}), 400

    email = body.get("emailid") or body.get("email")
    password = body.get("password")

    ok, missing = _require_str({"email": email, "password": password}, "email", "password")
    if not ok:
        logger.warning("[user_maintenance][DELETE /api/users] missing/invalid fields: %s", missing)
        return jsonify({"error": "missing required fields"}), 400

    logger.info("[user_maintenance][DELETE /api/users] invoking service")
    result = delete_user(  # type: ignore[arg-type]
        email=email,
        password=password,
    )
    logger.info("[user_maintenance][DELETE /api/users] finished with status_code=%s", result.get("status_code"))
    return _service_result_to_response(result)

