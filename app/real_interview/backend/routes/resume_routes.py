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
