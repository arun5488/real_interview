from typing import Any, Dict

from app.real_interview import logger
from app.real_interview.backend.services.job_application import get_job_application_for_customer
from app.real_interview.backend.services.pdfreader import resume_reader


def load_interview_context(
    *,
    customer_id: str,
    resume_id: str,
    job_application_id: str,
) -> Dict[str, Any]:
    """Load resume and job application from MongoDB (no LLM)."""
    logger.info(
        "[interview_context_loader] loading context customer_id=%s resume_id=%s job_application_id=%s",
        customer_id,
        resume_id,
        job_application_id,
    )
    reader = resume_reader()
    try:
        resume = reader.get_resume_for_user(customer_id, resume_id)
    finally:
        reader.close()

    job = get_job_application_for_customer(customer_id, job_application_id)
    target_role = (job.get("job_role") or "").strip()

    return {
        "parsed_data": resume.get("parsed_data") or {},
        "job_role": target_role,
        "job_description": job.get("job_description") or "",
        "application_link": job.get("application_link") or "",
    }
