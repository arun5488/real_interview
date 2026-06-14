from typing import Any, Dict

from app.real_interview import logger
from app.real_interview.backend.services.interview_record import (
    count_interviews_for_candidate,
    list_interviews_for_candidate_by_kind,
)
from app.real_interview.backend.services.user_interview_preferences import (
    build_max_questions_setting_payload,
)


def get_user_profile(*, customer_id: str, email: str) -> Dict[str, Any]:
    counts = count_interviews_for_candidate(customer_id)
    logger.info(
        "[user_profile] customer_id=%s completed=%s paused=%s",
        customer_id,
        counts["completed"],
        counts["paused"],
    )
    return {
        "status_code": 200,
        "email": email,
        "interview_counts": counts,
        "interview_settings": {
            "max_questions_per_interviewer": build_max_questions_setting_payload(customer_id),
        },
    }


def list_profile_interviews(*, customer_id: str, kind: str) -> Dict[str, Any]:
    interviews = list_interviews_for_candidate_by_kind(customer_id, kind)
    return {
        "status_code": 200,
        "kind": kind.strip().lower(),
        "interviews": interviews,
        "count": len(interviews),
    }
