import re
from typing import Any, Dict

from langchain_core.messages import AIMessage

from app.real_interview import logger
from app.real_interview.backend.agents.feedback_agent import FeedbackAgent
from app.real_interview.backend.agents.hr_recruiter_agent import HrRecruiterAgent
from app.real_interview.backend.agents.interviewer_agent import InterviewerAgent
from app.real_interview.backend.agents.router_agent import RouterAgent
from app.real_interview.backend.agents.summarizer_agent import SummarizerAgent
from app.real_interview.backend.config.configuration import get_summarizer_config
from app.real_interview.backend.services.interview_context_loader import load_interview_context
from app.real_interview.backend.services.question_bank import (
    append_questions_to_bank,
    extract_question_from_message,
    filter_seeds_for_interviewer,
    hash_question_text,
    load_question_seeds,
)
from app.real_interview.backend.state.interview_pipeline_state import InterviewPipelineState


def _estimate_tokens(messages: list) -> int:
    text = ""
    for m in messages:
        text += str(getattr(m, "content", ""))
    return max(1, len(text) // 4)


def _summarizer_threshold() -> int:
    return int(get_summarizer_config().get("token_threshold", 1500))


def _interviewer_code(interviewer_index: int) -> str:
    """Public label for interviewers in chat (I1, I2, …)."""
    return f"I{interviewer_index + 1}"


def _prefix_interviewer_message(content: str, interviewer_index: int) -> str:
    """Prefix assistant message with I1/I2 instead of agent personality names."""
    text = (content or "").strip()
    text = re.sub(r"^\[[^\]]+\]:\s*", "", text, count=1)
    return f"[{_interviewer_code(interviewer_index)}]: {text}"


def _experience_level_from_state(state: InterviewPipelineState) -> str:
    plan = state.get("panel_plan") or {}
    return (plan.get("experience_level") or "junior").strip() or "junior"


def _track_asked_question(content: str, asked_hashes: list[str]) -> list[str]:
    """Append hash for the question in an interviewer message, if detectable."""
    question = extract_question_from_message(content)
    if not question:
        return asked_hashes
    qh = hash_question_text(question)
    if qh in asked_hashes:
        return asked_hashes
    return [*asked_hashes, qh]


def _seeds_for_interviewer(state: InterviewPipelineState, interviewer_type: str) -> list[dict[str, Any]]:
    asked = set(state.get("asked_question_hashes") or [])
    seeds = state.get("question_bank_seeds") or []
    return filter_seeds_for_interviewer(seeds, asked, interviewer_type)


def _update_question_bank_from_messages(
    state: InterviewPipelineState,
    new_messages: list,
) -> dict[str, Any]:
    """Extract new questions via summarizer and append to Mongo bank (never raises)."""
    job_role = (state.get("job_role") or "").strip()
    if not job_role or not new_messages:
        return {}

    experience_level = _experience_level_from_state(state)
    agent = SummarizerAgent()
    extracted = agent.extract_questions_for_bank(
        new_messages=new_messages,
        job_role=job_role,
        experience_level=experience_level,
    )
    if not extracted:
        return {}

    added = append_questions_to_bank(job_role, experience_level, extracted, source="interview")
    if added <= 0:
        return {}

    seeds = load_question_seeds(job_role, experience_level)
    logger.info(
        "[interview_nodes] question_bank updated added=%s seeds=%s role=%s level=%s",
        added,
        len(seeds),
        job_role,
        experience_level,
    )
    return {"question_bank_seeds": seeds}


def load_context_node(state: InterviewPipelineState) -> Dict[str, Any]:
    logger.info("[interview_nodes] load_context customer_id=%s", state.get("customer_id"))
    try:
        ctx = load_interview_context(
            customer_id=state["customer_id"],
            resume_id=state["resume_id"],
            job_application_id=state["job_application_id"],
        )
        return {
            **ctx,
            "step": "loaded",
            "active_interviewer_index": 0,
            "interviewer_conclusions": [],
            "question_bank_seeds": state.get("question_bank_seeds") or [],
            "asked_question_hashes": state.get("asked_question_hashes") or [],
            "running_summary": state.get("running_summary") or "",
            "summary_snapshots": state.get("summary_snapshots") or [],
            "interview_complete": False,
        }
    except Exception as exc:
        logger.exception("[interview_nodes] load_context failed")
        return {"error": str(exc), "step": "failed"}


def hr_recruiter_node(state: InterviewPipelineState) -> Dict[str, Any]:
    logger.info("[interview_nodes] hr_recruiter")
    if state.get("error"):
        logger.warning("[interview_nodes] hr_recruiter skipped due to error")
        return {}
    agent = HrRecruiterAgent()
    impression = agent.analyze(
        parsed_data=state.get("parsed_data") or {},
        job_role=state.get("job_role") or "",
        job_description=state.get("job_description") or "",
    )
    logger.info("[interview_nodes] hr_recruiter complete candidate=%s", impression.get("candidate_name"))
    return {"first_impression": impression, "step": "hr_complete"}


def router_node(state: InterviewPipelineState) -> Dict[str, Any]:
    logger.info("[interview_nodes] router")
    if state.get("error"):
        return {}
    agent = RouterAgent()
    plan = agent.build_panel_plan(state.get("first_impression") or {})
    job_role = state.get("job_role") or ""
    experience_level = (plan.get("experience_level") or "junior").strip() or "junior"
    seeds = load_question_seeds(job_role, experience_level)
    logger.info(
        "[interview_nodes] router panel_size=%s bank_seeds=%s level=%s",
        plan.get("panel_size"),
        len(seeds),
        experience_level,
    )
    return {
        "panel_plan": plan,
        "question_bank_seeds": seeds,
        "asked_question_hashes": state.get("asked_question_hashes") or [],
        "step": "routed",
    }


def interviewer_opening_node(state: InterviewPipelineState) -> Dict[str, Any]:
    logger.info("[interview_nodes] interviewer_opening")
    if state.get("error"):
        return {}
    plan = state.get("panel_plan") or {}
    selected = plan.get("selected_interviewers") or []
    idx = int(state.get("active_interviewer_index") or 0)
    if idx >= len(selected):
        return {"step": "interview_ready", "interview_complete": False}

    interviewer_type = selected[idx]
    impression = state.get("first_impression") or {}
    candidate_role = impression.get("candidate_role") or state.get("job_role") or ""

    agent = InterviewerAgent()
    bank_seeds = _seeds_for_interviewer(state, interviewer_type)
    opening = agent.opening_message(
        interviewer_type=interviewer_type,
        candidate_role=candidate_role,
        parsed_data=state.get("parsed_data") or {},
        first_impression=impression,
        interview_summary=state.get("running_summary") or "",
        question_bank_seeds=bank_seeds,
    )
    if isinstance(opening.content, str):
        opening.content = _prefix_interviewer_message(opening.content, idx)

    asked = list(state.get("asked_question_hashes") or [])
    if isinstance(opening.content, str):
        asked = _track_asked_question(opening.content, asked)

    return {
        "messages": [opening],
        "asked_question_hashes": asked,
        "step": "interview_ready",
    }


def interviewer_turn_node(state: InterviewPipelineState) -> Dict[str, Any]:
    logger.info("[interview_nodes] interviewer_turn")
    if state.get("error") or state.get("interview_complete"):
        return {}

    plan = state.get("panel_plan") or {}
    selected = plan.get("selected_interviewers") or []
    idx = int(state.get("active_interviewer_index") or 0)
    if idx >= len(selected):
        return {"step": "awaiting_feedback"}

    interviewer_type = selected[idx]
    impression = state.get("first_impression") or {}
    candidate_role = impression.get("candidate_role") or state.get("job_role") or ""

    agent = InterviewerAgent()
    bank_seeds = _seeds_for_interviewer(state, interviewer_type)
    reply = agent.run_turn(
        interviewer_type=interviewer_type,
        candidate_role=candidate_role,
        parsed_data=state.get("parsed_data") or {},
        first_impression=impression,
        messages=list(state.get("messages") or []),
        interview_summary=state.get("running_summary") or "",
        question_bank_seeds=bank_seeds,
    )
    if isinstance(reply.content, str):
        reply.content = _prefix_interviewer_message(reply.content, idx)

    asked = list(state.get("asked_question_hashes") or [])
    if isinstance(reply.content, str):
        asked = _track_asked_question(reply.content, asked)

    return {
        "messages": [reply],
        "asked_question_hashes": asked,
        "step": "interview_turn",
    }


def maybe_summarize_node(state: InterviewPipelineState) -> Dict[str, Any]:
    messages = list(state.get("messages") or [])
    force = bool(state.get("force_summarize"))
    threshold = _summarizer_threshold()
    tokens = _estimate_tokens(messages)
    logger.info(
        "[interview_nodes] maybe_summarize tokens=%s threshold=%s force=%s",
        tokens,
        threshold,
        force,
    )
    if not force and tokens < threshold:
        return {}

    last_count = int(state.get("last_summarized_message_count") or 0)
    new_messages = messages[last_count:]
    if not new_messages:
        return {}

    prior = state.get("running_summary") or ""
    agent = SummarizerAgent()
    segment = agent.summarize_increment(new_messages=new_messages, prior_summary=prior)
    bank_update = _update_question_bank_from_messages(state, new_messages)

    if not segment.strip():
        out: Dict[str, Any] = {"last_summarized_message_count": len(messages)}
        out.update(bank_update)
        return out

    from app.real_interview.backend.services.interview_record import append_summary_text

    appended = append_summary_text(prior, segment)
    snapshots = list(state.get("summary_snapshots") or [])
    snapshots.append(segment)
    logger.info("[interview_nodes] summary appended total_chars=%s", len(appended))
    out = {
        "running_summary": appended,
        "summary_snapshots": snapshots,
        "last_summarized_message_count": len(messages),
        "step": "summarized",
    }
    out.update(bank_update)
    return out


def advance_interviewer_node(state: InterviewPipelineState) -> Dict[str, Any]:
    plan = state.get("panel_plan") or {}
    selected = plan.get("selected_interviewers") or []
    idx = int(state.get("active_interviewer_index") or 0) + 1
    logger.info("[interview_nodes] advance_interviewer next_index=%s", idx)
    if idx < len(selected):
        return {"active_interviewer_index": idx, "step": "advance_interviewer"}
    return {"interview_complete": True, "step": "interviews_done"}


def feedback_node(state: InterviewPipelineState) -> Dict[str, Any]:
    logger.info("[interview_nodes] feedback")
    if state.get("error"):
        return {}
    summary = state.get("running_summary") or ""
    agent = FeedbackAgent()
    feedback = agent.generate_feedback(
        interview_summary=summary,
        role_applied_for=state.get("job_role") or "",
        messages=list(state.get("messages") or []),
        first_impression=state.get("first_impression") or {},
    )
    return {
        "candidate_post_interview_feedback": feedback,
        "step": "complete",
        "interview_complete": True,
    }


def should_summarize(state: InterviewPipelineState) -> str:
    if _estimate_tokens(list(state.get("messages") or [])) >= _summarizer_threshold():
        return "summarize"
    return "skip_summarize"


def route_after_start(state: InterviewPipelineState) -> str:
    if state.get("error"):
        return "end"
    return "continue"
