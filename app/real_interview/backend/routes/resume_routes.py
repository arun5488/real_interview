from typing import Any, Dict

from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError

from app.real_interview import logger
from app.real_interview.backend.services.pdfreader import resume_reader

resume_blueprint = Blueprint("resume", __name__, url_prefix="/api")


def _public_resume_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    """Omit large `raw_text` from HTTP responses; full text remains in MongoDB."""
    out = {k: v for k, v in result.items() if k != "raw_text"}
    ts = out.get("uploaded_ts")
    if hasattr(ts, "isoformat"):
        out["uploaded_ts"] = ts.isoformat()
    return out


def _userid_from_request() -> str | None:
    userid = request.args.get("userid") or request.args.get("user_id")
    if userid and isinstance(userid, str) and userid.strip():
        return userid.strip()
    if request.is_json:
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            uid = body.get("userid") or body.get("user_id")
            if isinstance(uid, str) and uid.strip():
                return uid.strip()
    return None


@resume_blueprint.route("/resumes", methods=["GET"])
def list_resumes_route():
    logger.info("[resume][GET /api/resumes] start")
    userid = _userid_from_request()
    if not userid:
        logger.warning("[resume][GET /api/resumes] missing userid")
        return jsonify({"error": "missing or invalid userid"}), 400

    reader: resume_reader | None = None
    try:
        reader = resume_reader()
        resumes = reader.list_resumes_for_user(userid)
    except ValueError as exc:
        logger.warning("[resume][GET /api/resumes] validation error: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except PyMongoError:
        logger.exception("[resume][GET /api/resumes] MongoDB error")
        return jsonify({"error": "storage error"}), 500
    except Exception:
        logger.exception("[resume][GET /api/resumes] unexpected error")
        return jsonify({"error": "failed to list resumes"}), 500
    finally:
        if reader is not None:
            reader.close()

    return jsonify({"resumes": resumes, "count": len(resumes)}), 200


@resume_blueprint.route("/resumes/<resume_id>", methods=["GET"])
def get_resume_route(resume_id: str):
    logger.info("[resume][GET /api/resumes/%s] start", resume_id)
    userid = _userid_from_request()
    if not userid:
        return jsonify({"error": "missing or invalid userid"}), 400

    reader: resume_reader | None = None
    try:
        reader = resume_reader()
        resume = reader.get_resume_for_user(userid, resume_id)
    except ValueError as exc:
        logger.warning("[resume][GET /api/resumes/%s] %s", resume_id, exc)
        status = 404 if "not found" in str(exc).lower() else 400
        return jsonify({"error": str(exc)}), status
    except PyMongoError:
        logger.exception("[resume][GET /api/resumes/%s] MongoDB error", resume_id)
        return jsonify({"error": "storage error"}), 500
    except Exception:
        logger.exception("[resume][GET /api/resumes/%s] unexpected error", resume_id)
        return jsonify({"error": "failed to load resume"}), 500
    finally:
        if reader is not None:
            reader.close()

    return jsonify({"resume": resume}), 200


@resume_blueprint.route("/resumes", methods=["POST"])
def upload_resume_route():
    logger.info("[resume][POST /api/resumes] start")

    userid = request.form.get("userid") or request.form.get("user_id")
    if not userid or not isinstance(userid, str) or not userid.strip():
        logger.warning("[resume][POST /api/resumes] missing or invalid userid")
        return jsonify({"error": "missing or invalid userid"}), 400

    file_storage = None
    for key in ("resume", "file", "pdf"):
        if key in request.files:
            file_storage = request.files.get(key)
            break

    if file_storage is None or not getattr(file_storage, "filename", None):
        logger.warning("[resume][POST /api/resumes] missing file")
        return (
            jsonify(
                {
                    "error": "missing resume file (form field: resume, file, or pdf)",
                }
            ),
            400,
        )

    reader: resume_reader | None = None
    try:
        reader = resume_reader()
        data = reader.read_pdf_stream(
            file_storage.stream,
            filename=file_storage.filename,
            content_type=file_storage.content_type,
        )
        result = reader.save_resume(
            userid.strip(),
            data,
            file_storage.filename,
            content_type=file_storage.content_type,
        )
    except ValueError as exc:
        logger.warning("[resume][POST /api/resumes] validation error: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except PyMongoError:
        logger.exception("[resume][POST /api/resumes] MongoDB error")
        return jsonify({"error": "storage error"}), 500
    except Exception:
        logger.exception("[resume][POST /api/resumes] unexpected error")
        return jsonify({"error": "failed to process resume"}), 500
    finally:
        if reader is not None:
            reader.close()

    logger.info(
        "[resume][POST /api/resumes] finished resume_id=%s",
        result.get("_id"),
    )
    return jsonify({"message": "resume uploaded successfully", "resume": _public_resume_payload(result)}), 201
