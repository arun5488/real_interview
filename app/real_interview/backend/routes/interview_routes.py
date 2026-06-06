from typing import Any, Dict, Tuple

from flask import Blueprint, g, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.auth.jwt_auth import interview_session_owned_by, require_auth
from app.real_interview.backend.services.job_application import get_job_application_for_customer
from app.real_interview.backend.services.interview_service import (
    advance_to_next_interviewer,
    complete_interview,
    get_interview_state,
    pause_interview,
    resume_interview,
    send_interview_message,
    start_interview,
)
from app.real_interview.backend.services.pdfreader import resume_reader

interview_blueprint = Blueprint("interview", __name__, url_prefix="/api")


def _parse_json_body() -> Dict[str, Any] | None:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return None
    return data


def _response(result: Dict[str, Any]):
    code = int(result.pop("status_code", 200))
    return jsonify(result), code


def _forbidden(message: str = "access denied"):
    return jsonify({"error": message}), 403


def _verify_interview_session(session_id: str) -> Tuple[bool, Any]:
    if not interview_session_owned_by(session_id, g.current_user_id):
        return False, _forbidden("interview session not found or access denied")
    return True, None


def _verify_start_resources(resume_id: str, job_application_id: str) -> Tuple[bool, Any]:
    reader: resume_reader | None = None
    try:
        reader = resume_reader()
        reader.get_resume_for_user(g.current_user_id, resume_id)
        get_job_application_for_customer(g.current_user_id, job_application_id)
        return True, None
    except ValueError as exc:
        logger.warning("[interview] start resource check failed: %s", exc)
        return False, (jsonify({"error": str(exc)}), 404)
    finally:
        if reader is not None:
            reader.close()


@interview_blueprint.route("/interview/start", methods=["POST"])
@require_auth
def interview_start_route():
    logger.info("[interview][POST /api/interview/start]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    resume_id = body.get("resume_id")
    job_application_id = body.get("job_application_id")

    if not all(isinstance(x, str) and x.strip() for x in (resume_id, job_application_id)):
        return jsonify({"error": "resume_id and job_application_id are required"}), 400

    ok, err = _verify_start_resources(resume_id.strip(), job_application_id.strip())
    if not ok:
        return err

    result = start_interview(
        customer_id=g.current_user_id,
        resume_id=resume_id.strip(),
        job_application_id=job_application_id.strip(),
    )
    return _response(result)


@interview_blueprint.route("/interview/message", methods=["POST"])
@require_auth
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

    session_id = session_id.strip()
    ok, err = _verify_interview_session(session_id)
    if not ok:
        return err

    logger.info("[interview][POST /api/interview/message] session_id=%s", session_id)
    result = send_interview_message(session_id=session_id, message=message)
    return _response(result)


@interview_blueprint.route("/interview/advance", methods=["POST"])
@require_auth
def interview_advance_route():
    logger.info("[interview][POST /api/interview/advance]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_interview_session(session_id)
    if not ok:
        return err

    result = advance_to_next_interviewer(session_id=session_id)
    return _response(result)


@interview_blueprint.route("/interview/pause", methods=["POST"])
@require_auth
def interview_pause_route():
    logger.info("[interview][POST /api/interview/pause]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_interview_session(session_id)
    if not ok:
        return err

    result = pause_interview(session_id=session_id)
    return _response(result)


@interview_blueprint.route("/interview/resume", methods=["POST"])
@require_auth
def interview_resume_route():
    logger.info("[interview][POST /api/interview/resume]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_interview_session(session_id)
    if not ok:
        return err

    result = resume_interview(session_id=session_id)
    return _response(result)


@interview_blueprint.route("/interview/complete", methods=["POST"])
@require_auth
def interview_complete_route():
    logger.info("[interview][POST /api/interview/complete]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id") or body.get("thread_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_interview_session(session_id)
    if not ok:
        return err

    result = complete_interview(session_id=session_id)
    return _response(result)


@interview_blueprint.route("/interview/state", methods=["GET"])
@require_auth
def interview_state_route():
    session_id = request.args.get("session_id") or request.args.get("thread_id")
    if not session_id or not session_id.strip():
        return jsonify({"error": "session_id query parameter is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_interview_session(session_id)
    if not ok:
        return err

    logger.info("[interview][GET /api/interview/state] session_id=%s", session_id)
    result = get_interview_state(session_id=session_id)
    return _response(result)


@interview_blueprint.route("/interview/record", methods=["GET"])
@require_auth
def interview_record_route():
    session_id = request.args.get("session_id") or request.args.get("thread_id")
    if not session_id or not session_id.strip():
        return jsonify({"error": "session_id query parameter is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_interview_session(session_id)
    if not ok:
        return err

    logger.info("[interview][GET /api/interview/record] session_id=%s", session_id)
    result = get_interview_state(session_id=session_id)
    return _response(result)
