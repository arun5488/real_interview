from typing import Any, Dict

from app.real_interview import logger
from app.real_interview.backend.services.interview_closing import (
    MIN_MAX_QUESTIONS_PER_INTERVIEWER,
    default_max_questions_per_interviewer,
)
from app.real_interview.backend.services.user_maintenance import (
    get_user_max_questions_override,
    set_user_max_questions_override,
)


def resolve_max_questions_per_interviewer_for_user(user_id: str) -> int:
    """Effective limit: user override in authentications, else params.yaml default."""
    override = get_user_max_questions_override(user_id)
    if override is not None:
        return override
    return default_max_questions_per_interviewer()


def build_max_questions_setting_payload(user_id: str) -> Dict[str, Any]:
    override = get_user_max_questions_override(user_id)
    default = default_max_questions_per_interviewer()
    effective = override if override is not None else default
    return {
        "default": default,
        "minimum": MIN_MAX_QUESTIONS_PER_INTERVIEWER,
        "override": override,
        "effective": effective,
    }


def update_max_questions_per_interviewer_preference(
    user_id: str,
    value: int | None,
) -> Dict[str, Any]:
    result = set_user_max_questions_override(user_id, value)
    status_code = int(result.get("status_code", 200))
    if status_code != 200:
        return result

    logger.info(
        "[user_interview_preferences] updated max_questions user_id=%s override=%s effective=%s",
        user_id,
        get_user_max_questions_override(user_id),
        resolve_max_questions_per_interviewer_for_user(user_id),
    )
    payload = build_max_questions_setting_payload(user_id)
    return {
        "status_code": 200,
        "message": result.get("message") or "interview setting saved",
        "interview_settings": {"max_questions_per_interviewer": payload},
    }
