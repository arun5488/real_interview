from typing import Any, Dict, List

from app.real_interview import logger
from app.real_interview.backend.agents.candidate_avatar_agent import CandidateAvatarAgent
from app.real_interview.backend.services.pdfreader import resume_reader


def _latest_resume_id(resumes: List[Dict[str, Any]]) -> str:
    if not resumes:
        return ""
    return str(resumes[0].get("resume_id") or "").strip()


def get_avatar_discuss_context(*, customer_id: str) -> Dict[str, Any]:
    """Return whether the user can discuss with avatar (requires at least one resume)."""
    reader = resume_reader()
    try:
        resumes = reader.list_resumes_for_user(customer_id)
        if not resumes:
            return {
                "status_code": 200,
                "ready": False,
                "message": "Upload a resume on your profile to use Discuss with Avatar.",
            }
        resume_id = _latest_resume_id(resumes)
        resume = reader.get_resume_for_user(customer_id, resume_id)
        parsed = resume.get("parsed_data") or {}
        name = (parsed.get("name") or "").strip() if isinstance(parsed, dict) else ""
        label = resume.get("label") or resumes[0].get("label") or "Resume"
        role = ""
        if isinstance(parsed, dict):
            roles = parsed.get("roles") or parsed.get("experience") or []
            if isinstance(roles, list) and roles:
                first = roles[0]
                if isinstance(first, dict):
                    role = (first.get("title") or first.get("role") or "").strip()
        return {
            "status_code": 200,
            "ready": True,
            "resume_id": resume_id,
            "resume_label": label,
            "candidate_name": name,
            "suggested_role": role,
            "message": "Ask any interview question. Your ideal avatar will answer from your resume.",
        }
    except Exception:
        logger.exception("[avatar_discuss] get context failed customer_id=%s", customer_id)
        return {"status_code": 500, "error": "could not load avatar context"}
    finally:
        reader.close()


def discuss_with_avatar(
    *,
    customer_id: str,
    message: str,
    history: List[Dict[str, str]] | None = None,
    resume_id: str | None = None,
) -> Dict[str, Any]:
    question = (message or "").strip()
    if not question:
        return {"status_code": 400, "error": "message is required"}

    if len(question) > 4000:
        return {"status_code": 400, "error": "message is too long (max 4000 characters)"}

    reader = resume_reader()
    try:
        resumes = reader.list_resumes_for_user(customer_id)
        if not resumes:
            return {
                "status_code": 409,
                "error": "Upload a resume on your profile before using Discuss with Avatar.",
            }

        chosen_id = (resume_id or "").strip() or _latest_resume_id(resumes)
        resume = reader.get_resume_for_user(customer_id, chosen_id)
        parsed_data = resume.get("parsed_data") or {}

        role = ""
        if isinstance(parsed_data, dict):
            roles = parsed_data.get("roles") or parsed_data.get("experience") or []
            if isinstance(roles, list) and roles:
                first = roles[0]
                if isinstance(first, dict):
                    role = (first.get("title") or first.get("role") or "").strip()

        agent = CandidateAvatarAgent()
        answer = agent.answer_interview_question(
            parsed_data=parsed_data,
            job_role=role,
            question=question,
            history=history,
        )
        return {
            "status_code": 200,
            "resume_id": chosen_id,
            "question": question,
            "ideal_answer": answer.get("ideal_answer") or "",
            "web_sources": answer.get("web_sources") or [],
        }
    except ValueError as exc:
        return {"status_code": 404, "error": str(exc)}
    except Exception:
        logger.exception("[avatar_discuss] discuss failed customer_id=%s", customer_id)
        return {"status_code": 500, "error": "could not generate avatar answer"}
    finally:
        reader.close()
