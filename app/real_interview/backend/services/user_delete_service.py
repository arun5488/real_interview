import os
from typing import Any, Dict

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.real_interview import logger
from app.real_interview.backend.services.pdfreader import resume_reader
from app.real_interview.backend.services.user_maintenance import (
    _check_password,
    _error,
    _get_client_and_collection,
    _success,
)
from app.real_interview.backend.utils.mongodb import connect_mongodb


def _get_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _get_job_applications_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_JOB_APPLICATIONS", "job_application").strip()


def _get_interview_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_INTERVIEW", "interview").strip()


def _delete_job_applications_for_customer(db, customer_oid: ObjectId) -> int:
    coll_name = _get_job_applications_collection_name()
    logger.info("[user_delete] deleting job_application docs for customer_id=%s", customer_oid)
    result = db[coll_name].delete_many({"customer_id": customer_oid})
    count = int(result.deleted_count)
    logger.info("[user_delete] deleted %s job_application document(s)", count)
    return count


def _delete_interview_records_for_customer(db, customer_oid: ObjectId) -> int:
    coll_name = _get_interview_collection_name()
    logger.info("[user_delete] deleting interview docs for candidate_id=%s", customer_oid)
    result = db[coll_name].delete_many({"customer_id": customer_oid})
    count = int(result.deleted_count)
    logger.info("[user_delete] deleted %s interview document(s)", count)
    return count


def delete_user_account(email: str, password: str) -> Dict[str, Any]:
    """
    Verify email/password, then remove the user from authentications and delete
    related resumes (including GridFS), job_application, and interview records.
    """
    logger.info("[user_delete] delete_user_account start email=%s", email)
    auth_client = None
    reader: resume_reader | None = None

    try:
        if not isinstance(email, str) or not email.strip():
            logger.warning("[user_delete] invalid email")
            return _error(422, "email does not exist")

        if not isinstance(password, str) or not password:
            logger.warning("[user_delete] missing password")
            return _error(423, "invalid email or password")

        auth_client, auth_coll = _get_client_and_collection()
        user_doc = auth_coll.find_one({"email": email.strip()})
        if not user_doc:
            logger.warning("[user_delete] user not found email=%s", email)
            return _error(422, "email does not exist")

        stored_hash = user_doc.get("password")
        if not stored_hash or not isinstance(stored_hash, str):
            logger.warning("[user_delete] missing password hash")
            return _error(423, "invalid email or password")

        if not _check_password(password, stored_hash):
            logger.warning("[user_delete] password mismatch email=%s", email)
            return _error(423, "invalid email or password")

        user_oid = user_doc["_id"]
        if not isinstance(user_oid, ObjectId):
            return _error(422, "email does not exist")

        reader = resume_reader()
        resumes_deleted, gridfs_deleted = reader.delete_all_resumes_for_user(user_oid)

        db = auth_client[_get_db_name()]
        jobs_deleted = _delete_job_applications_for_customer(db, user_oid)
        interviews_deleted = _delete_interview_records_for_customer(db, user_oid)

        delete_result = auth_coll.delete_one({"_id": user_oid})
        if delete_result.deleted_count != 1:
            logger.error("[user_delete] failed to delete auth record user_id=%s", user_oid)
            return _error(500, "failed to delete user account")

        logger.info(
            "[user_delete] account removed user_id=%s resumes=%s gridfs=%s jobs=%s interviews=%s",
            user_oid,
            resumes_deleted,
            gridfs_deleted,
            jobs_deleted,
            interviews_deleted,
        )
        return _success(
            200,
            {
                "message": "user and related data deleted successfully",
                "deleted": {
                    "authentications": 1,
                    "resumes": resumes_deleted,
                    "gridfs_files": gridfs_deleted,
                    "job_application": jobs_deleted,
                    "interview": interviews_deleted,
                },
            },
        )

    except PyMongoError:
        logger.exception("[user_delete] MongoDB error")
        raise
    except Exception:
        logger.exception("[user_delete] unexpected error")
        raise
    finally:
        if reader is not None:
            reader.close()
        if auth_client is not None:
            auth_client.close()
