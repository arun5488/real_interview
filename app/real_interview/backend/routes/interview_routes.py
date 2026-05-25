from typing import Any, Dict

from flask import Blueprint, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.services.interview_service import (
    advance_to_next_interviewer,
    complete_interview,
    get_interview_state,
    pause_interview,
    resume_interview,
    send_interview_message,
    start_interview,
)

interview_blueprint = Blueprint("interview", __name__, url_prefix="/api")


def _parse_json_body() -> Dict[str, Any] | None:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return None
    return data


def _response(result: Dict[str, Any]):
    code = int(result.pop("status_code", 200))
    return jsonify(result), code


@interview_blueprint.route("/interview/start", methods=["POST"])
def interview_start_route():
    logger.info("[interview][POST /api/interview/start]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    customer_id = body.get("customer_id") or body.get("userid") or body.get("user_id")
    resume_id = body.get("resume_id")
    job_application_id = body.get("job_application_id")

    if not all(isinstance(x, str) and x.strip() for x in (customer_id, resume_id, job_application_id)):
        return jsonify({"error": "customer_id, resume_id, and job_application_id are required"}), 400

    result = start_interview(
        customer_id=customer_id.strip(),
        resume_id=resume_id.strip(),
        job_application_id=job_application_id.strip(),
    )
    return _response(result)


@interview_blueprint.route("/interview/message", methods=["POST"])
def interview_message_route():
    logger.info("[interview][POST /api/interview/message]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    message = body.get("message")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "message is required"}), 400

    logger.info("[interview][POST /api/interview/message] session_id=%s", session_id.strip())
    result = send_interview_message(session_id=session_id.strip(), message=message)
    return _response(result)


@interview_blueprint.route("/interview/advance", methods=["POST"])
def interview_advance_route():
    logger.info("[interview][POST /api/interview/advance]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    result = advance_to_next_interviewer(session_id=session_id.strip())
    return _response(result)


@interview_blueprint.route("/interview/pause", methods=["POST"])
def interview_pause_route():
    logger.info("[interview][POST /api/interview/pause]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    result = pause_interview(session_id=session_id.strip())
    return _response(result)


@interview_blueprint.route("/interview/resume", methods=["POST"])
def interview_resume_route():
    logger.info("[interview][POST /api/interview/resume]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    result = resume_interview(session_id=session_id.strip())
    return _response(result)


@interview_blueprint.route("/interview/complete", methods=["POST"])
def interview_complete_route():
    logger.info("[interview][POST /api/interview/complete]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    result = complete_interview(session_id=session_id.strip())
    return _response(result)


@interview_blueprint.route("/interview/state", methods=["GET"])
def interview_state_route():
    session_id = request.args.get("session_id") or request.args.get("thread_id")
    if not session_id or not session_id.strip():
        return jsonify({"error": "session_id query parameter is required"}), 400
    logger.info("[interview][GET /api/interview/state] session_id=%s", session_id.strip())
    result = get_interview_state(session_id=session_id.strip())
    return _response(result)


@interview_blueprint.route("/interview/record", methods=["GET"])
def interview_record_route():
    session_id = request.args.get("session_id") or request.args.get("thread_id")
    if not session_id or not session_id.strip():
        return jsonify({"error": "session_id query parameter is required"}), 400
    logger.info("[interview][GET /api/interview/record] session_id=%s", session_id.strip())
    result = get_interview_state(session_id=session_id.strip())
    return _response(result)
