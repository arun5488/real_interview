from typing import Any, Dict

from app.real_interview import logger
from app.real_interview.backend.services.interview_closing import (
    MIN_MAX_QUESTIONS_PER_INTERVIEWER,
    default_max_questions_per_interviewer,
)
from app.real_interview.backend.services.user_maintenance import (
    get_user_max_questions_override,
    is_ideal_answer_report_enabled,
    set_ideal_answer_report_enabled,
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


def build_ideal_answer_report_setting_payload(user_id: str) -> Dict[str, Any]:
    enabled = is_ideal_answer_report_enabled(user_id)
    return {
        "enabled": enabled,
        "default_enabled": True,
        "description": (
            "Completed interview reports include ideal answers grounded in your resume "
            "(with optional web sources). Applies to past and new completed sessions."
        ),
    }


def build_interview_settings_payload(user_id: str) -> Dict[str, Any]:
    return {
        "max_questions_per_interviewer": build_max_questions_setting_payload(user_id),
        "ideal_answer_report": build_ideal_answer_report_setting_payload(user_id),
    }


def update_interview_settings(
    user_id: str,
    *,
    max_questions_per_interviewer: int | None | object = ...,
    ideal_answer_report_enabled: bool | None = None,
) -> Dict[str, Any]:
    """
    Update one or more interview preferences on the authentications document.

    Pass max_questions_per_interviewer=... only when updating that field.
    """
    messages: list[str] = []

    if max_questions_per_interviewer is not ...:
        result = set_user_max_questions_override(user_id, max_questions_per_interviewer)  # type: ignore[arg-type]
        status_code = int(result.get("status_code", 200))
        if status_code != 200:
            return result
        messages.append(str(result.get("message") or "interview setting saved"))

    if ideal_answer_report_enabled is not None:
        result = set_ideal_answer_report_enabled(user_id, ideal_answer_report_enabled)
        status_code = int(result.get("status_code", 200))
        if status_code != 200:
            return result
        messages.append(str(result.get("message") or "interview setting saved"))

    if not messages:
        return {"status_code": 400, "error": "no interview settings provided"}

    logger.info("[user_interview_preferences] updated settings user_id=%s", user_id)
    return {
        "status_code": 200,
        "message": messages[-1],
        "interview_settings": build_interview_settings_payload(user_id),
    }


def update_max_questions_per_interviewer_preference(
    user_id: str,
    value: int | None,
) -> Dict[str, Any]:
    return update_interview_settings(user_id, max_questions_per_interviewer=value)
