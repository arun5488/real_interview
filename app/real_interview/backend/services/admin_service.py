import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pymongo.errors import PyMongoError

from app.real_interview import logger
from app.real_interview.backend.utils.mongodb import get_mongodb_database


def _db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _users_collection() -> str:
    return os.getenv("MONGODB_COLLECTION_USERS", "authentications").strip()


def _interviews_collection() -> str:
    return os.getenv("MONGODB_COLLECTION_INTERVIEW", "interview").strip()


def _resumes_collection() -> str:
    return os.getenv("MONGODB_COLLECTION_RESUMES", "resumes").strip()


def _jobs_collection() -> str:
    return os.getenv("MONGODB_COLLECTION_JOB_APPLICATIONS", "job_application").strip()


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _start_of_day_utc(now: datetime) -> datetime:
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def _active_candidate_ids(users) -> List[Any]:
    """User ids still present in authentications (excludes deleted accounts)."""
    return [doc["_id"] for doc in users.find({}, {"_id": 1})]


def _interviews_for_active_candidates(active_ids: List[Any]) -> Dict[str, Any]:
    """Mongo filter: interviews whose candidate still has an account."""
    if not active_ids:
        return {"candidate_id": {"$exists": False}}  # match nothing
    return {"candidate_id": {"$in": active_ids}}


def get_admin_dashboard(*, days: int = 30, user_limit: int = 50) -> Dict[str, Any]:
    """Aggregate signups and interview usage metrics for the admin dashboard."""
    days = max(1, min(int(days), 365))
    user_limit = max(1, min(int(user_limit), 200))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    today_start = _start_of_day_utc(now)
    week_start = now - timedelta(days=7)

    try:
        db = get_mongodb_database(_db_name())
        users = db[_users_collection()]
        interviews = db[_interviews_collection()]
        resumes = db[_resumes_collection()]
        jobs = db[_jobs_collection()]

        active_candidate_ids = _active_candidate_ids(users)
        active_interviews = _interviews_for_active_candidates(active_candidate_ids)

        total_users = users.count_documents({})
        users_new_period = users.count_documents({"created_ts": {"$gte": since}})
        users_new_7d = users.count_documents({"created_ts": {"$gte": week_start}})
        users_new_today = users.count_documents({"created_ts": {"$gte": today_start}})

        interviews_total = interviews.count_documents(active_interviews)
        interviews_active = interviews.count_documents(
            {**active_interviews, "interview_status": "active"}
        )
        interviews_paused = interviews.count_documents(
            {**active_interviews, "interview_status": "paused"}
        )
        interviews_completed = interviews.count_documents(
            {
                **active_interviews,
                "$or": [
                    {"interview_status": "completed"},
                    {"interview_feedback": {"$exists": True, "$ne": None}},
                ],
            }
        )
        interviews_in_period = interviews.count_documents(
            {**active_interviews, "interview_date": {"$gte": since}}
        )
        interviews_not_started = interviews.count_documents(
            {
                **active_interviews,
                "$or": [
                    {"messages": {"$exists": False}},
                    {"messages": {"$size": 0}},
                ],
            }
        )

        recent_users: List[Dict[str, Any]] = []
        for doc in users.find({}, {"email": 1, "created_ts": 1}).sort("created_ts", -1).limit(user_limit):
            recent_users.append(
                {
                    "user_id": str(doc["_id"]),
                    "email": doc.get("email") or "",
                    "created_at": _iso(doc.get("created_ts")),
                }
            )

        email_by_id: Dict[str, str] = {
            str(doc["_id"]): doc.get("email") or ""
            for doc in users.find({}, {"email": 1})
        }

        recent_interviews: List[Dict[str, Any]] = []
        for doc in interviews.find(
            active_interviews,
            {
                "session_id": 1,
                "candidate_id": 1,
                "role_applied_for": 1,
                "interview_status": 1,
                "interview_date": 1,
                "paused_at": 1,
                "messages": 1,
                "interview_feedback": 1,
            },
        ).sort("interview_date", -1).limit(user_limit):
            candidate_id = doc.get("candidate_id")
            candidate_key = str(candidate_id) if candidate_id is not None else ""
            message_count = len(doc.get("messages") or [])
            status = doc.get("interview_status") or "active"
            if doc.get("interview_feedback"):
                status = "completed"
            recent_interviews.append(
                {
                    "session_id": doc.get("session_id") or "",
                    "candidate_id": candidate_key,
                    "candidate_email": email_by_id.get(candidate_key, ""),
                    "role_applied_for": doc.get("role_applied_for") or "",
                    "interview_status": status,
                    "interview_date": _iso(doc.get("interview_date")),
                    "paused_at": _iso(doc.get("paused_at")),
                    "message_count": message_count,
                }
            )

        return {
            "status_code": 200,
            "generated_at": now.isoformat(),
            "period_days": days,
            "metrics": {
                "users": {
                    "total": total_users,
                    "new_in_period": users_new_period,
                    "new_last_7_days": users_new_7d,
                    "new_today": users_new_today,
                },
                "interviews": {
                    "total": interviews_total,
                    "in_period": interviews_in_period,
                    "active": interviews_active,
                    "paused": interviews_paused,
                    "completed": interviews_completed,
                    "not_started": interviews_not_started,
                },
                "resumes_total": resumes.count_documents({}),
                "job_applications_total": jobs.count_documents({}),
            },
            "recent_signups": recent_users,
            "recent_interviews": recent_interviews,
        }
    except PyMongoError:
        logger.exception("[admin_service] dashboard query failed")
        raise
