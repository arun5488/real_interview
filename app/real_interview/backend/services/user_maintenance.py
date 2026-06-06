import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import bcrypt
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.real_interview import logger
from app.real_interview.backend.auth.email_utils import find_user_by_email, normalize_email
from app.real_interview.backend.utils.mongodb import connect_mongodb


def _success(status_code: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status_code": status_code}
    if payload:
        result.update(payload)
    return result


def _error(status_code: int, message: str) -> Dict[str, Any]:
    return {"status_code": status_code, "error": message}


def _get_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _get_users_collection_name() -> str:
    # Contract says collection: `authentications` (provided in `.env` as `MONGODB_COLLECTION_USERS`)
    return os.getenv("MONGODB_COLLECTION_USERS", "authentications").strip()


def _ensure_indexes(collection) -> None:
    logger.info("[user_maintenance] ensuring unique index on `email`")
    # Enforce unique email at the DB level.
    collection.create_index([("email", 1)], unique=True, name="unique_email")
    logger.info("[user_maintenance] unique index ready")


def _get_client_and_collection():
    logger.info("[user_maintenance] opening MongoDB connection")
    client = connect_mongodb()
    db = client[_get_db_name()]
    collection = db[_get_users_collection_name()]
    _ensure_indexes(collection)
    return client, collection


def _password_meets_complexity(password: str) -> bool:
    # Complexity rules:
    # - minimum 8 characters
    # - at least 1 special (non alphanumeric)
    # - at least 1 numeric
    # - at least 1 letter
    if not isinstance(password, str):
        return False
    if len(password) < 8:
        return False
    if not re.search(r"[A-Za-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True


def _hash_password(password: str) -> str:
    # bcrypt returns bytes; we store as utf-8 string.
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def _check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def sign_up_user(email: str, password: str, confirm_password: str) -> Dict[str, Any]:
    """
    POST: sign up user

    Input: email id, password, confirm password
    Response: user id created successfully

    Error codes:
      409 - email already exists
      423 - password mismatch or weak password
    """
    logger.info("[user_maintenance][POST] sign_up_user start")
    client = None

    try:
        email = normalize_email(email)
        if not email:
            logger.warning("[user_maintenance][POST] invalid email input")
            return _error(423, "password mismatch or weak password")

        if password != confirm_password:
            logger.warning("[user_maintenance][POST] password mismatch")
            return _error(423, "password mismatch or weak password")

        if not _password_meets_complexity(password):
            logger.warning("[user_maintenance][POST] weak password")
            return _error(423, "password mismatch or weak password")

        client, collection = _get_client_and_collection()

        logger.info("[user_maintenance][POST] checking if email exists: %s", email)
        if find_user_by_email(collection, email):
            logger.warning("[user_maintenance][POST] email already exists")
            return _error(409, "email already exists")

        created_ts = datetime.now(timezone.utc)
        hashed_password = _hash_password(password)
        logger.info("[user_maintenance][POST] inserting new user")

        try:
            result = collection.insert_one(
                {
                    "email": email,
                    "password": hashed_password,
                    "created_ts": created_ts,
                }
            )
        except DuplicateKeyError:
            # Race condition: another request inserted same email.
            logger.warning("[user_maintenance][POST] duplicate key on insert (email exists)")
            return _error(409, "email already exists")

        user_id = str(result.inserted_id)
        logger.info(f"[user_maintenance][POST] user created successfully: {user_id}")
        return _success(
            201,
            {"user_id": user_id, "email": email, "message": "user created successfully"},
        )

    except PyMongoError:
        logger.exception("[user_maintenance][POST] MongoDB error")
        raise
    except Exception:
        logger.exception("[user_maintenance][POST] unexpected error")
        raise
    finally:
        if client is not None:
            logger.info("[user_maintenance][POST] closing MongoDB connection")
            client.close()


def login_user(email: str, password: str) -> Dict[str, Any]:
    """
    POST: sign in with email and password.

    Response: user_id on success.

    Error codes:
      401 - invalid email or password
    """
    logger.info("[user_maintenance][POST] login_user start")
    client = None

    try:
        email = normalize_email(email)
        if not email:
            logger.warning("[user_maintenance][POST] login invalid email")
            return _error(401, "invalid email or password")

        if not isinstance(password, str) or not password:
            logger.warning("[user_maintenance][POST] login invalid password")
            return _error(401, "invalid email or password")

        client, collection = _get_client_and_collection()

        user_doc = find_user_by_email(collection, email)
        if not user_doc:
            logger.warning("[user_maintenance][POST] login user not found")
            return _error(401, "invalid email or password")

        stored_hash = user_doc.get("password")
        if not stored_hash or not isinstance(stored_hash, str):
            logger.warning("[user_maintenance][POST] login missing password hash")
            return _error(401, "invalid email or password")

        if not _check_password(password, stored_hash):
            logger.warning("[user_maintenance][POST] login password mismatch")
            return _error(401, "invalid email or password")

        user_id = str(user_doc["_id"])
        user_email = user_doc.get("email") or email
        logger.info("[user_maintenance][POST] login success for user_id=%s", user_id)
        return _success(
            200,
            {"user_id": user_id, "email": user_email, "message": "signed in successfully"},
        )

    except PyMongoError:
        logger.exception("[user_maintenance][POST] login MongoDB error")
        raise
    except Exception:
        logger.exception("[user_maintenance][POST] login unexpected error")
        raise
    finally:
        if client is not None:
            logger.info("[user_maintenance][POST] closing MongoDB connection")
            client.close()


def change_password(
    email: str,
    current_password: str,
    new_password: str,
    confirm_new_password: str,
) -> Dict[str, Any]:
    """
    PUT: Change Password

    Input: email, current password, new password, confirm new password
    Response: password changed successfully

    Error codes:
      401 - current password incorrect
      422 - email does not exist
      423 - password mismatch or weak password
    """
    logger.info("[user_maintenance][PUT] change_password start")
    client = None

    try:
        email = normalize_email(email)
        if not email:
            logger.warning("[user_maintenance][PUT] invalid email input")
            return _error(422, "email doesnot exist")

        if not isinstance(current_password, str) or not current_password:
            logger.warning("[user_maintenance][PUT] missing current password")
            return _error(401, "current password is incorrect")

        if new_password != confirm_new_password:
            logger.warning("[user_maintenance][PUT] password mismatch")
            return _error(423, "password mismatch or weak password")

        if not _password_meets_complexity(new_password):
            logger.warning("[user_maintenance][PUT] weak password")
            return _error(423, "password mismatch or weak password")

        client, collection = _get_client_and_collection()

        logger.info("[user_maintenance][PUT] checking if user exists: %s", email)
        user_doc = find_user_by_email(collection, email)
        if not user_doc:
            logger.warning("[user_maintenance][PUT] email does not exist")
            return _error(422, "email doesnot exist")

        stored_hash = user_doc.get("password")
        if not stored_hash or not isinstance(stored_hash, str):
            return _error(401, "current password is incorrect")
        if not _check_password(current_password, stored_hash):
            logger.warning("[user_maintenance][PUT] current password mismatch")
            return _error(401, "current password is incorrect")

        logger.info("[user_maintenance][PUT] updating password")
        hashed_password = _hash_password(new_password)
        update_result = collection.update_one(
            {"email": email},
            {"$set": {"password": hashed_password}},
        )

        if update_result.matched_count != 1:
            # Extremely unlikely because we already fetched the user_doc.
            logger.warning("[user_maintenance][PUT] unexpected update result")
            return _error(422, "email doesnot exist")

        logger.info("[user_maintenance][PUT] password changed successfully")
        return _success(200, {"message": "password changed successfully"})

    except PyMongoError:
        logger.exception("[user_maintenance][PUT] MongoDB error")
        raise
    except Exception:
        logger.exception("[user_maintenance][PUT] unexpected error")
        raise
    finally:
        if client is not None:
            logger.info("[user_maintenance][PUT] closing MongoDB connection")
            client.close()


def delete_user(email: str, password: str) -> Dict[str, Any]:
    """
    DELETE: remove user from authentications and cascade-delete related data.

    Delegates to user_delete_service (resumes, job_application, interview).
    """
    from app.real_interview.backend.services.user_delete_service import delete_user_account

    logger.info("[user_maintenance][DELETE] delete_user delegating to user_delete_service")
    return delete_user_account(email=email, password=password)

