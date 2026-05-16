from typing import Any, Dict

from flask import Blueprint, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.services.job_application import submit_job_application

job_application_blueprint = Blueprint("job_application", __name__, url_prefix="/api")


def _parse_json_body() -> Dict[str, Any] | None:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return None
    return data


def _service_result_to_response(result: Dict[str, Any]):
    status_code = int(result.pop("status_code", 200))
    return jsonify(result), status_code


@job_application_blueprint.route("/job-applications", methods=["POST"])
def submit_job_application_route():
    logger.info("[job_application][POST /api/job-applications] start")
    body = _parse_json_body()
    if body is None:
        logger.warning("[job_application][POST /api/job-applications] invalid JSON body")
        return jsonify({"error": "invalid JSON body"}), 400

    customer_id = body.get("customer_id") or body.get("userid") or body.get("user_id")
    input_mode = body.get("input_mode") or body.get("mode")
    application_link = body.get("application_link") or body.get("job_link")
    job_description_text = (
        body.get("job_description_text")
        or body.get("job_description")
        or body.get("description")
    )

    if not isinstance(customer_id, str) or not customer_id.strip():
        return jsonify({"error": "missing or invalid customer_id"}), 400
    if not isinstance(input_mode, str) or not input_mode.strip():
        return jsonify({"error": "missing or invalid input_mode"}), 400

    logger.info("[job_application][POST /api/job-applications] invoking service")
    result = submit_job_application(
        customer_id=customer_id.strip(),
        input_mode=input_mode.strip(),
        application_link=application_link if isinstance(application_link, str) else None,
        job_description_text=(
            job_description_text if isinstance(job_description_text, str) else None
        ),
    )
    logger.info(
        "[job_application][POST /api/job-applications] finished status_code=%s",
        result.get("status_code"),
    )
    return _service_result_to_response(result)
