from typing import Any, Dict, Tuple

from app.real_interview import logger
from app.real_interview.backend.agents.candidate_avatar_agent import CandidateAvatarAgent
from app.real_interview.backend.services.interview_context_loader import load_interview_context
from app.real_interview.backend.services.interview_qa_extract import extract_interview_qa_pairs
from app.real_interview.backend.services.interview_record import (
    clear_ideal_answers_reports_for_candidate,
    get_interview_by_session,
    save_ideal_answers_report,
)
from app.real_interview.backend.services.user_maintenance import is_ideal_answer_report_enabled


def _resolve_interview_ids(
    doc: Dict[str, Any],
    session_id: str,
    customer_id: str,
) -> Tuple[str, str, str]:
    """Resolve candidate, resume, and job ids (supports older completed records)."""
    resolved_customer = str(doc.get("candidate_id") or customer_id or "").strip()
    resume_id = str(doc.get("resume_id") or "").strip()
    job_application_id = str(doc.get("job_application_id") or "").strip()

    sid = (session_id or doc.get("session_id") or "").strip()
    if sid:
        parts = sid.split(":", 2)
        if len(parts) == 3:
            if not resolved_customer:
                resolved_customer = parts[0].strip()
            if not resume_id:
                resume_id = parts[1].strip()
            if not job_application_id:
                job_application_id = parts[2].strip()

    return resolved_customer, resume_id, job_application_id


def _load_avatar_context(
    *,
    customer_id: str,
    resume_id: str,
    job_application_id: str,
    role_applied_for: str,
) -> Dict[str, Any]:
    fallback: Dict[str, Any] = {
        "parsed_data": {},
        "job_role": role_applied_for or "",
        "job_description": "",
        "application_link": "",
    }
    if not resume_id or not job_application_id:
        return fallback

    try:
        return load_interview_context(
            customer_id=customer_id,
            resume_id=resume_id,
            job_application_id=job_application_id,
        )
    except Exception:
        logger.warning(
            "[ideal_answer_report] full context load failed customer_id=%s resume_id=%s job_id=%s",
            customer_id,
            resume_id,
            job_application_id,
        )

    try:
        from app.real_interview.backend.services.pdfreader import resume_reader

        reader = resume_reader()
        try:
            resume = reader.get_resume_for_user(customer_id, resume_id)
        finally:
            reader.close()
        fallback["parsed_data"] = resume.get("parsed_data") or {}
    except Exception:
        logger.warning("[ideal_answer_report] resume-only fallback failed resume_id=%s", resume_id)

    return fallback


def _should_use_cached_report(existing: Any, qa_pairs: list) -> bool:
    if not isinstance(existing, dict):
        return False
    items = existing.get("items")
    if not isinstance(items, list):
        return False
    if len(items) > 0:
        return True
    # Retry generation when a prior run cached empty but Q&A exists now.
    return len(qa_pairs) == 0


def ensure_ideal_answers_report(
    *,
    session_id: str,
    customer_id: str,
    record: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    """
    Generate and persist ideal answers when the user has enabled the feature.

    Works for existing completed interviews on first report view/download.
    Returns the report dict, or None when disabled / not applicable.
    """
    if not is_ideal_answer_report_enabled(customer_id):
        return None

    doc = record or get_interview_by_session(session_id)
    if not doc:
        return None

    qa_pairs = extract_interview_qa_pairs(doc.get("messages") or [])
    existing = doc.get("ideal_answers_report")
    if _should_use_cached_report(existing, qa_pairs):
        return existing  # type: ignore[return-value]

    resolved_customer, resume_id, job_application_id = _resolve_interview_ids(
        doc, session_id, customer_id
    )
    if not resolved_customer:
        resolved_customer = customer_id

    if not qa_pairs:
        empty = {
            "avatar_summary": "No technical Q&A pairs were found to generate ideal answers.",
            "items": [],
        }
        save_ideal_answers_report(session_id, empty)
        return empty

    ctx = _load_avatar_context(
        customer_id=resolved_customer,
        resume_id=resume_id,
        job_application_id=job_application_id,
        role_applied_for=doc.get("role_applied_for") or "",
    )

    agent = CandidateAvatarAgent()
    report = agent.generate_ideal_answers(
        parsed_data=ctx.get("parsed_data") or {},
        job_role=doc.get("role_applied_for") or ctx.get("job_role") or "",
        job_description=ctx.get("job_description") or "",
        qa_pairs=qa_pairs,
        interview_summary=doc.get("interview_summary") or "",
    )
    save_ideal_answers_report(session_id, report)
    logger.info(
        "[ideal_answer_report] saved session_id=%s items=%s (existing_completed=%s)",
        session_id,
        len(report.get("items") or []),
        bool(existing),
    )
    return report


def refresh_ideal_answers_for_completed_interviews(customer_id: str) -> int:
    """
    Clear cached ideal-answer reports so completed sessions regenerate on next download.

    Called when a user explicitly re-enables the feature.
    """
    cleared = clear_ideal_answers_reports_for_candidate(customer_id)
    logger.info(
        "[ideal_answer_report] cleared cached reports customer_id=%s count=%s",
        customer_id,
        cleared,
    )
    return cleared
