from flask import Blueprint, g, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.auth.admin_auth import is_admin_email, require_admin
from app.real_interview.backend.auth.jwt_auth import require_auth
from app.real_interview.backend.services.admin_service import get_admin_dashboard

admin_blueprint = Blueprint("admin", __name__, url_prefix="/api/admin")


def _response(result: dict):
    code = int(result.pop("status_code", 200))
    return jsonify(result), code


@admin_blueprint.route("/access", methods=["GET"])
@require_auth
def admin_access_route():
    """Check whether the signed-in user may open the admin dashboard."""
    allowed = is_admin_email(g.current_user_email or "")
    return jsonify(
        {
            "is_admin": allowed,
            "email": g.current_user_email,
        }
    ), 200


@admin_blueprint.route("/dashboard", methods=["GET"])
@require_admin
def admin_dashboard_route():
    logger.info("[admin][GET /api/admin/dashboard] user_id=%s", g.current_user_id)
    days_raw = request.args.get("days", "30")
    limit_raw = request.args.get("limit", "50")
    try:
        days = int(days_raw)
        limit = int(limit_raw)
    except ValueError:
        return jsonify({"error": "days and limit must be integers"}), 400

    result = get_admin_dashboard(days=days, user_limit=limit)
    return _response(result)
