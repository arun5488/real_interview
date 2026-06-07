import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo.errors import CollectionInvalid, PyMongoError

from app.real_interview import logger
from app.real_interview.backend.config.configuration import get_summarizer_config
from app.real_interview.backend.utils.mongodb import connect_mongodb


def _get_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _get_interview_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_INTERVIEW", "interview").strip()


def _as_object_id(value: str, field_name: str) -> ObjectId:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    try:
        return ObjectId(value.strip())
    except InvalidId as exc:
        raise ValueError(f"{field_name} is not a valid ObjectId") from exc


def _get_collection() -> tuple[Any, Collection]:
    client = connect_mongodb()
    db = client[_get_db_name()]
    coll_name = _get_interview_collection_name()
    names = set(db.list_collection_names())
    if coll_name not in names:
        try:
            db.create_collection(coll_name)
            logger.info("[interview_record] created collection %r", coll_name)
        except CollectionInvalid:
            logger.warning("[interview_record] collection %r already exists (race)", coll_name)
    collection = db[coll_name]
    collection.create_index([("session_id", 1)], unique=True, name="unique_session_id")
    collection.create_index([("candidate_id", 1), ("interview_date", -1)], name="candidate_interview_date")
    return client, collection


def append_summary_text(existing: str, new_part: str) -> str:
    """Append summarizer output to prior summary (never replace)."""
    prior = (existing or "").strip()
    chunk = (new_part or "").strip()
    if not chunk:
        return prior
    if not prior:
        combined = chunk
    else:
        combined = f"{prior}\n\n---\n\n{chunk}"
    max_chars = int(get_summarizer_config().get("max_summary_chars", 8000))
    if len(combined) > max_chars:
        logger.info(
            "[interview_record] truncating summary from %s to %s chars",
            len(combined),
            max_chars,
        )
        combined = combined[-max_chars:]
    return combined


def create_interview_record(
    *,
    session_id: str,
    candidate_id: str,
    resume_id: str,
    job_application_id: str,
    role_applied_for: str,
) -> Dict[str, Any]:
    logger.info("[interview_record] create session_id=%s candidate_id=%s", session_id, candidate_id)
    client = None
    try:
        candidate_oid = _as_object_id(candidate_id, "candidate_id")
        client, collection = _get_collection()
        interview_date = datetime.now(timezone.utc)
        doc = {
            "session_id": session_id,
            "candidate_id": candidate_oid,
            "resume_id": resume_id,
            "job_application_id": job_application_id,
            "interview_date": interview_date,
            "role_applied_for": role_applied_for or "",
            "interview_status": "active",
            "paused_at": None,
            "interview_summary": "",
            "interview_feedback": None,
            "messages": [],
            "last_summarized_message_count": 0,
        }
        result = collection.insert_one(doc)
        logger.info("[interview_record] created interview_id=%s", result.inserted_id)
        return {
            "interview_id": str(result.inserted_id),
            "session_id": session_id,
            "interview_date": interview_date.isoformat(),
        }
    finally:
        if client is not None:
            client.close()


def list_session_ids_for_candidate(candidate_id: str) -> List[str]:
    """Return interview session_ids owned by a candidate."""
    client = None
    try:
        candidate_oid = _as_object_id(candidate_id, "candidate_id")
        client, collection = _get_collection()
        cursor = collection.find({"candidate_id": candidate_oid}, {"session_id": 1})
        return [doc["session_id"] for doc in cursor if doc.get("session_id")]
    finally:
        if client is not None:
            client.close()


def _serialize_session_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    interview_date = doc.get("interview_date")
    paused_at = doc.get("paused_at")
    return {
        "session_id": doc.get("session_id"),
        "resume_id": doc.get("resume_id"),
        "job_application_id": doc.get("job_application_id"),
        "role_applied_for": doc.get("role_applied_for") or "",
        "interview_status": doc.get("interview_status") or "active",
        "interview_date": interview_date.isoformat() if hasattr(interview_date, "isoformat") else interview_date,
        "paused_at": paused_at.isoformat() if hasattr(paused_at, "isoformat") else paused_at,
    }


def list_open_interviews_for_candidate(candidate_id: str) -> List[Dict[str, Any]]:
    """Return paused or in-progress interviews (not completed), newest first."""
    client = None
    try:
        candidate_oid = _as_object_id(candidate_id, "candidate_id")
        client, collection = _get_collection()
        query: Dict[str, Any] = {
            "candidate_id": candidate_oid,
            "interview_status": {"$in": ["paused", "active"]},
            "$or": [
                {"interview_feedback": None},
                {"interview_feedback": {"$exists": False}},
            ],
        }
        cursor = collection.find(
            query,
            {
                "session_id": 1,
                "resume_id": 1,
                "job_application_id": 1,
                "role_applied_for": 1,
                "interview_status": 1,
                "interview_date": 1,
                "paused_at": 1,
            },
        ).sort("interview_date", -1)
        return [_serialize_session_summary(doc) for doc in cursor if doc.get("session_id")]
    finally:
        if client is not None:
            client.close()


def get_interview_by_session(session_id: str) -> Optional[Dict[str, Any]]:
    logger.info("[interview_record] get_by_session session_id=%s", session_id)
    client = None
    try:
        client, collection = _get_collection()
        doc = collection.find_one({"session_id": session_id})
        if not doc:
            logger.warning("[interview_record] no record for session_id=%s", session_id)
            return None
        return _serialize_doc(doc)
    finally:
        if client is not None:
            client.close()


def append_chat_messages(session_id: str, messages: List[Dict[str, str]]) -> None:
    if not messages:
        return
    logger.info("[interview_record] append %s message(s) session_id=%s", len(messages), session_id)
    client = None
    try:
        client, collection = _get_collection()
        stamped = []
        now = datetime.now(timezone.utc)
        for m in messages:
            stamped.append(
                {
                    "role": m.get("role", "user"),
                    "content": m.get("content", ""),
                    "ts": now,
                }
            )
        collection.update_one(
            {"session_id": session_id},
            {"$push": {"messages": {"$each": stamped}}},
        )
    finally:
        if client is not None:
            client.close()


def set_interview_summary(session_id: str, summary: str) -> None:
    logger.info("[interview_record] set summary session_id=%s chars=%s", session_id, len(summary or ""))
    client = None
    try:
        client, collection = _get_collection()
        collection.update_one(
            {"session_id": session_id},
            {"$set": {"interview_summary": summary or ""}},
        )
    finally:
        if client is not None:
            client.close()


def append_interview_summary(session_id: str, new_summary_part: str) -> str:
    logger.info("[interview_record] append summary session_id=%s", session_id)
    client = None
    try:
        client, collection = _get_collection()
        doc = collection.find_one({"session_id": session_id}, {"interview_summary": 1})
        if not doc:
            raise ValueError("interview record not found")
        updated = append_summary_text(doc.get("interview_summary") or "", new_summary_part)
        collection.update_one(
            {"session_id": session_id},
            {"$set": {"interview_summary": updated}},
        )
        return updated
    finally:
        if client is not None:
            client.close()


def set_last_summarized_message_count(session_id: str, count: int) -> None:
    client = None
    try:
        client, collection = _get_collection()
        collection.update_one(
            {"session_id": session_id},
            {"$set": {"last_summarized_message_count": count}},
        )
    finally:
        if client is not None:
            client.close()


def get_message_count(session_id: str) -> int:
    doc = get_interview_by_session(session_id)
    if not doc:
        return 0
    return len(doc.get("messages") or [])


def set_interview_status(session_id: str, status: str) -> None:
    """Set interview_status to active, paused, or completed."""
    logger.info("[interview_record] set status session_id=%s status=%s", session_id, status)
    client = None
    try:
        client, collection = _get_collection()
        update: Dict[str, Any] = {"interview_status": status}
        if status == "paused":
            update["paused_at"] = datetime.now(timezone.utc)
        elif status == "active":
            update["paused_at"] = None
        collection.update_one({"session_id": session_id}, {"$set": update})
    finally:
        if client is not None:
            client.close()


def save_interview_feedback(session_id: str, feedback: Dict[str, Any]) -> None:
    logger.info("[interview_record] save feedback session_id=%s", session_id)
    client = None
    try:
        client, collection = _get_collection()
        collection.update_one(
            {"session_id": session_id},
            {"$set": {"interview_feedback": feedback}},
        )
    finally:
        if client is not None:
            client.close()


def _serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    interview_date = doc.get("interview_date")
    paused_at = doc.get("paused_at")
    return {
        "interview_id": str(doc["_id"]),
        "session_id": doc.get("session_id"),
        "candidate_id": str(doc.get("candidate_id", "")),
        "resume_id": doc.get("resume_id"),
        "job_application_id": doc.get("job_application_id"),
        "interview_date": interview_date.isoformat() if hasattr(interview_date, "isoformat") else interview_date,
        "role_applied_for": doc.get("role_applied_for") or "",
        "interview_status": doc.get("interview_status") or "active",
        "paused_at": paused_at.isoformat() if hasattr(paused_at, "isoformat") else paused_at,
        "interview_summary": doc.get("interview_summary") or "",
        "interview_feedback": doc.get("interview_feedback"),
        "messages": [
            {
                "role": m.get("role"),
                "content": m.get("content"),
                "ts": m.get("ts").isoformat() if hasattr(m.get("ts"), "isoformat") else m.get("ts"),
            }
            for m in (doc.get("messages") or [])
        ],
        "last_summarized_message_count": int(doc.get("last_summarized_message_count") or 0),
    }
