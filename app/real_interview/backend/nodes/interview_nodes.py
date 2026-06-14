import re
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage

from app.real_interview import logger
from app.real_interview.backend.agents.feedback_agent import FeedbackAgent
from app.real_interview.backend.agents.hr_recruiter_agent import HrRecruiterAgent
from app.real_interview.backend.agents.interviewer_agent import InterviewerAgent
from app.real_interview.backend.agents.panel_coordinator_agent import PanelCoordinatorAgent
from app.real_interview.backend.agents.router_agent import RouterAgent
from app.real_interview.backend.agents.summarizer_agent import SummarizerAgent
from app.real_interview.backend.config.configuration import get_summarizer_config
from app.real_interview.backend.services.interview_closing import (
    all_panelists_at_question_limit,
    ask_candidate_questions_message,
    candidate_asked_question,
    candidate_declined_questions,
    counts_for_state,
    counts_from_state,
    increment_interviewer_question_count,
    max_candidate_qa_turns,
    panel_closing_message,
    question_limit_from_state,
)
from app.real_interview.backend.services.question_bank import (
    append_questions_to_bank,
    extract_question_from_message,
    filter_seeds_for_interviewer,
    hash_question_text,
    load_question_seeds,
)
from app.real_interview.backend.services.interview_context_loader import load_interview_context
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


def _question_limit(state: InterviewPipelineState) -> int:
    return question_limit_from_state(state)


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


def _message_counts_as_question(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    if extract_question_from_message(text):
        return True
    return "?" in text


def _last_human_text(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


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
        from app.real_interview.backend.services.user_interview_preferences import (
            resolve_max_questions_per_interviewer_for_user,
        )

        ctx = load_interview_context(
            customer_id=state["customer_id"],
            resume_id=state["resume_id"],
            job_application_id=state["job_application_id"],
        )
        question_limit = resolve_max_questions_per_interviewer_for_user(state["customer_id"])
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
            "interview_phase": "active",
            "interviewer_question_counts": state.get("interviewer_question_counts") or {},
            "max_questions_per_interviewer": question_limit,
            "candidate_qa_turns": int(state.get("candidate_qa_turns") or 0),
            "pending_auto_complete": False,
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


def _run_panel_speakers(
    state: InterviewPipelineState,
    speaker_indices: list[int],
    *,
    opening: bool,
    question_counts: dict[int, int] | None = None,
) -> Dict[str, Any]:
    plan = state.get("panel_plan") or {}
    selected = plan.get("selected_interviewers") or []
    panel_size = len(selected)
    if not selected:
        return {"step": "interview_ready"}

    counts = dict(question_counts or counts_from_state(state.get("interviewer_question_counts"), panel_size))
    limit = _question_limit(state)
    impression = state.get("first_impression") or {}
    candidate_role = impression.get("candidate_role") or state.get("job_role") or ""
    agent = InterviewerAgent()
    base_messages = list(state.get("messages") or [])
    turn_messages: list = []
    asked = list(state.get("asked_question_hashes") or [])
    out_messages: list[AIMessage] = []

    for order, idx in enumerate(speaker_indices):
        if idx >= len(selected):
            continue
        if not opening and counts.get(idx, 0) >= limit:
            continue
        interviewer_type = selected[idx]
        local_state: InterviewPipelineState = {**state, "asked_question_hashes": asked}
        bank_seeds = _seeds_for_interviewer(local_state, interviewer_type)
        if opening:
            reply = agent.opening_message(
                interviewer_type=interviewer_type,
                candidate_role=candidate_role,
                parsed_data=state.get("parsed_data") or {},
                first_impression=impression,
                interview_summary=state.get("running_summary") or "",
                question_bank_seeds=bank_seeds,
                panel_plan=plan,
                interviewer_index=idx,
                is_lead=(order == 0),
                prior_messages=base_messages + turn_messages,
            )
        else:
            reply = agent.run_turn(
                interviewer_type=interviewer_type,
                candidate_role=candidate_role,
                parsed_data=state.get("parsed_data") or {},
                first_impression=impression,
                messages=base_messages + turn_messages,
                interview_summary=state.get("running_summary") or "",
                question_bank_seeds=bank_seeds,
                panel_plan=plan,
                interviewer_index=idx,
            )

        if isinstance(reply.content, str):
            reply.content = _prefix_interviewer_message(reply.content, idx)
            if _message_counts_as_question(reply.content):
                counts = increment_interviewer_question_count(counts, panel_size, idx)
            asked = _track_asked_question(reply.content, asked)
        turn_messages.append(reply)
        out_messages.append(reply)

    return {
        "messages": out_messages,
        "asked_question_hashes": asked,
        "interviewer_question_counts": counts_for_state(counts),
        "step": "interview_ready" if opening else "interview_turn",
    }


def _begin_awaiting_candidate_questions(state: InterviewPipelineState, counts: dict[int, int]) -> Dict[str, Any]:
    speaker_idx = 0
    return {
        "messages": [AIMessage(content=ask_candidate_questions_message(speaker_idx))],
        "interview_phase": "awaiting_candidate_questions",
        "interviewer_question_counts": counts_for_state(counts),
        "step": "awaiting_candidate_questions",
    }


def _finish_interview(state: InterviewPipelineState, counts: dict[int, int]) -> Dict[str, Any]:
    return {
        "messages": [AIMessage(content=panel_closing_message(0))],
        "interview_phase": "ended",
        "pending_auto_complete": True,
        "interview_complete": True,
        "interviewer_question_counts": counts_for_state(counts),
        "step": "interview_closing",
    }


def _run_candidate_qa_turn(
    state: InterviewPipelineState,
    counts: dict[int, int],
) -> Dict[str, Any]:
    plan = state.get("panel_plan") or {}
    selected = plan.get("selected_interviewers") or []
    if not selected:
        return _finish_interview(state, counts)

    idx = 0
    interviewer_type = selected[idx]
    impression = state.get("first_impression") or {}
    candidate_role = impression.get("candidate_role") or state.get("job_role") or ""
    agent = InterviewerAgent()
    reply = agent.run_turn(
        interviewer_type=interviewer_type,
        candidate_role=candidate_role,
        parsed_data=state.get("parsed_data") or {},
        first_impression=impression,
        messages=list(state.get("messages") or []),
        interview_summary=state.get("running_summary") or "",
        panel_plan=plan,
        interviewer_index=idx,
        turn_mode="candidate_qa",
    )
    if isinstance(reply.content, str):
        reply.content = _prefix_interviewer_message(reply.content, idx)

    qa_turns = int(state.get("candidate_qa_turns") or 0) + 1
    out_messages = [reply]
    result: Dict[str, Any] = {
        "messages": out_messages,
        "interview_phase": "candidate_qa",
        "candidate_qa_turns": qa_turns,
        "interviewer_question_counts": counts_for_state(counts),
        "step": "candidate_qa",
    }
    if qa_turns >= max_candidate_qa_turns():
        out_messages.append(AIMessage(content=panel_closing_message(idx)))
        result["interview_phase"] = "ended"
        result["pending_auto_complete"] = True
        result["interview_complete"] = True
        result["step"] = "interview_closing"
    return result


def panel_opening_node(state: InterviewPipelineState) -> Dict[str, Any]:
    logger.info("[interview_nodes] panel_opening")
    if state.get("error"):
        return {}
    plan = state.get("panel_plan") or {}
    selected = plan.get("selected_interviewers") or []
    if not selected:
        return {"step": "interview_ready", "interview_complete": False}

    coordinator = PanelCoordinatorAgent()
    speaker_indices = coordinator.plan_opening(plan)
    result = _run_panel_speakers(state, speaker_indices, opening=True)
    result["interview_complete"] = False
    result["interview_phase"] = "active"
    result["candidate_qa_turns"] = 0
    result["pending_auto_complete"] = False
    return result


def panel_turn_node(state: InterviewPipelineState) -> Dict[str, Any]:
    logger.info("[interview_nodes] panel_turn phase=%s", state.get("interview_phase") or "active")
    if state.get("error"):
        return {}

    plan = state.get("panel_plan") or {}
    selected = plan.get("selected_interviewers") or []
    panel_size = len(selected)
    if not panel_size:
        return {"step": "interview_turn"}

    counts = counts_from_state(state.get("interviewer_question_counts"), panel_size)
    phase = state.get("interview_phase") or "active"
    last_human = _last_human_text(list(state.get("messages") or []))

    if phase == "awaiting_candidate_questions":
        if candidate_declined_questions(last_human):
            logger.info("[interview_nodes] candidate declined panel questions; ending")
            return _finish_interview(state, counts)
        if candidate_asked_question(last_human) or last_human.strip():
            return _run_candidate_qa_turn(state, counts)
        return _finish_interview(state, counts)

    if phase == "candidate_qa":
        if candidate_declined_questions(last_human):
            return _finish_interview(state, counts)
        qa_turns = int(state.get("candidate_qa_turns") or 0)
        if qa_turns >= max_candidate_qa_turns():
            return _finish_interview(state, counts)
        return _run_candidate_qa_turn(state, counts)

    if all_panelists_at_question_limit(counts, panel_size, limit=_question_limit(state)):
        logger.info("[interview_nodes] all panelists reached question limit; inviting candidate questions")
        return _begin_awaiting_candidate_questions(state, counts)

    coordinator = PanelCoordinatorAgent()
    speaker_indices = coordinator.plan_follow_up(
        panel_plan=plan,
        messages=list(state.get("messages") or []),
        running_summary=state.get("running_summary") or "",
    )
    limit = _question_limit(state)
    speaker_indices = [idx for idx in speaker_indices if counts.get(idx, 0) < limit]

    if not speaker_indices:
        if all_panelists_at_question_limit(counts, panel_size, limit=limit):
            return _begin_awaiting_candidate_questions(state, counts)
        speaker_indices = [
            idx for idx, count in counts.items() if count < limit
        ][:1]

    result = _run_panel_speakers(state, speaker_indices, opening=False, question_counts=counts)
    result["interview_phase"] = "active"
    return result


def interviewer_opening_node(state: InterviewPipelineState) -> Dict[str, Any]:
    """Backward-compatible alias for panel opening."""
    return panel_opening_node(state)


def interviewer_turn_node(state: InterviewPipelineState) -> Dict[str, Any]:
    """Backward-compatible alias for panel turn."""
    return panel_turn_node(state)


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
