import os
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.real_interview import logger
from app.real_interview.backend.auth.email_utils import find_user_by_id, normalize_email
from app.real_interview.backend.graphs.interview_graph import (
    get_advance_graph,
    get_chat_graph,
    get_feedback_graph,
    get_start_graph,
    make_thread_id,
)
from app.real_interview.backend.services import interview_record as interview_db
from app.real_interview.backend.services.email_service import (
    interview_feedback_email_enabled,
    is_smtp_available,
    send_interview_feedback_email,
)
from app.real_interview.backend.utils.mongodb import get_mongodb_database


def _users_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_USERS", "authentications").strip()


def _candidate_email_for_record(record: Dict[str, Any]) -> str:
    candidate_id = record.get("candidate_id")
    if not candidate_id:
        return ""
    users = get_mongodb_database()[_users_collection_name()]
    user_doc = find_user_by_id(users, str(candidate_id))
    if not user_doc:
        return ""
    return normalize_email(str(user_doc.get("email") or ""))


def _should_email_feedback(
    record: Dict[str, Any],
    *,
    email_feedback: bool | None,
) -> bool:
    if not interview_feedback_email_enabled() or not is_smtp_available():
        return False
    if record.get("feedback_email_sent"):
        return False
    if email_feedback is not None:
        return bool(email_feedback)
    return bool(record.get("email_feedback_opt_in"))


def _maybe_send_feedback_email(
    *,
    session_id: str,
    record: Dict[str, Any],
    feedback: Dict[str, Any],
    email_feedback: bool | None,
) -> tuple[bool, str]:
    if not _should_email_feedback(record, email_feedback=email_feedback):
        return False, ""
    candidate_email = _candidate_email_for_record(record)
    ok, err = send_interview_feedback_email(
        candidate_email=candidate_email,
        feedback=feedback,
        role_applied_for=record.get("role_applied_for") or "",
        session_id=session_id,
    )
    if ok:
        interview_db.mark_feedback_email_sent(session_id)
    return ok, err


def set_interview_preferences(
    *,
    session_id: str,
    email_feedback_opt_in: bool,
) -> Dict[str, Any]:
    record = interview_db.get_interview_by_session(session_id)
    if not record:
        return {"status_code": 404, "error": "interview session not found", "session_id": session_id}
    interview_db.set_email_feedback_opt_in(session_id, email_feedback_opt_in)
    record = interview_db.get_interview_by_session(session_id) or {}
    state = _get_merged_state(session_id)
    return {
        "status_code": 200,
        "session_id": session_id,
        "email_feedback_opt_in": bool(email_feedback_opt_in),
        "state": _public_state(state, record) if state else _public_state({"session_id": session_id}, record),
    }


def _config(thread_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _messages_from_record(record: Dict[str, Any]) -> List[BaseMessage]:
    out: List[BaseMessage] = []
    for m in record.get("messages") or []:
        content = m.get("content") or ""
        if m.get("role") == "user":
            out.append(HumanMessage(content=content))
        else:
            out.append(AIMessage(content=content))
    return out


def _message_to_dict(msg: BaseMessage) -> Dict[str, str]:
    role = "assistant"
    if isinstance(msg, HumanMessage):
        role = "user"
    elif isinstance(msg, AIMessage):
        role = "assistant"
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    return {"role": role, "content": content}


def _public_state(state: Dict[str, Any], record: Dict[str, Any] | None = None) -> Dict[str, Any]:
    messages = state.get("messages") or []
    if record and record.get("messages"):
        messages_out = record["messages"]
    else:
        messages_out = [_message_to_dict(m) for m in messages]

    summary = state.get("running_summary") or ""
    if record and record.get("interview_summary"):
        summary = record.get("interview_summary") or summary

    feedback = state.get("candidate_post_interview_feedback")
    if record and record.get("interview_feedback"):
        feedback = record.get("interview_feedback")

    interview_status = "active"
    if record:
        interview_status = record.get("interview_status") or "active"

    return {
        "session_id": state.get("session_id"),
        "interview_record_id": state.get("interview_record_id"),
        "customer_id": state.get("customer_id"),
        "resume_id": state.get("resume_id"),
        "job_application_id": state.get("job_application_id"),
        "job_role": state.get("job_role"),
        "first_impression": state.get("first_impression"),
        "panel_plan": state.get("panel_plan"),
        "active_interviewer_index": state.get("active_interviewer_index"),
        "running_summary": summary,
        "interview_status": interview_status,
        "interview_phase": state.get("interview_phase") or "active",
        "candidate_qa_turns": int(state.get("candidate_qa_turns") or 0),
        "interviewer_question_counts": state.get("interviewer_question_counts") or {},
        "email_feedback_opt_in": bool(record.get("email_feedback_opt_in")) if record else False,
        "feedback_email_sent": bool(record.get("feedback_email_sent")) if record else False,
        "candidate_post_interview_feedback": feedback,
        "interview_complete": state.get("interview_complete"),
        "step": state.get("step"),
        "error": state.get("error"),
        "messages": messages_out,
    }


def _get_merged_state(thread_id: str) -> Dict[str, Any]:
    graph = get_start_graph()
    snapshot = graph.get_state(_config(thread_id))
    if snapshot and snapshot.values:
        return dict(snapshot.values)
    return {}


def _restore_checkpoint_if_missing(session_id: str) -> None:
    """
    Rebuild LangGraph checkpoint from Mongo when checkpoints were cleared but
    the interview record still exists (fallback after manual DB cleanup).
    """
    state = _get_merged_state(session_id)
    if state.get("first_impression") and state.get("panel_plan"):
        return

    record = interview_db.get_interview_by_session(session_id)
    if not record or not (record.get("messages") or []):
        return

    parts = session_id.split(":", 2)
    if len(parts) != 3:
        return
    customer_id, resume_id, job_application_id = parts

    try:
        from app.real_interview.backend.nodes.interview_nodes import hr_recruiter_node, router_node
        from app.real_interview.backend.services.interview_context_loader import load_interview_context

        base: Dict[str, Any] = load_interview_context(
            customer_id=customer_id,
            resume_id=resume_id,
            job_application_id=job_application_id,
        )
        base.update(
            {
                "session_id": session_id,
                "interview_record_id": record.get("interview_id"),
                "messages": _messages_from_record(record),
                "running_summary": record.get("interview_summary") or "",
                "last_summarized_message_count": int(record.get("last_summarized_message_count") or 0),
                "active_interviewer_index": int(state.get("active_interviewer_index") or 0),
                "interview_complete": bool(state.get("interview_complete")),
                "interviewer_conclusions": state.get("interviewer_conclusions") or [],
            }
        )
        base.update(hr_recruiter_node(base))
        if base.get("error"):
            logger.warning("[interview_service] restore HR failed session_id=%s", session_id)
            return
        base.update(router_node(base))
        _patch_checkpoint(session_id, base)
        logger.info("[interview_service] restored checkpoint from Mongo session_id=%s", session_id)
    except Exception:
        logger.exception("[interview_service] checkpoint restore failed session_id=%s", session_id)


def _patch_checkpoint(session_id: str, values: Dict[str, Any]) -> None:
    if not values:
        return
    get_start_graph().update_state(_config(session_id), values)


def _merge_summary_from_record(state: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer the longer stored summary when checkpoint lags Mongo."""
    db_summary = (record.get("interview_summary") or "").strip()
    running = (state.get("running_summary") or "").strip()
    if db_summary and len(db_summary) >= len(running):
        state = dict(state)
        state["running_summary"] = db_summary
    last_db = int(record.get("last_summarized_message_count") or 0)
    last_state = int(state.get("last_summarized_message_count") or 0)
    if last_db > last_state:
        state["last_summarized_message_count"] = last_db
    return state


def _force_summarize(session_id: str) -> str:
    """Summarize all messages not yet covered (used on pause)."""
    from app.real_interview.backend.nodes.interview_nodes import maybe_summarize_node

    record = interview_db.get_interview_by_session(session_id) or {}
    state = _get_merged_state(session_id)
    if not state and record:
        state = {
            "session_id": session_id,
            "messages": _messages_from_record(record),
            "running_summary": record.get("interview_summary") or "",
            "last_summarized_message_count": int(record.get("last_summarized_message_count") or 0),
            "job_role": record.get("role_applied_for") or "",
        }
    elif state and not (state.get("messages") or []) and record.get("messages"):
        state = dict(state)
        state["messages"] = _messages_from_record(record)
    if state:
        state = _merge_summary_from_record(state, record)
        if not (state.get("job_role") or "").strip():
            state["job_role"] = record.get("role_applied_for") or ""
    state["session_id"] = session_id
    state["force_summarize"] = True
    update = maybe_summarize_node(state)
    if update:
        state.update(update)
        _patch_checkpoint(session_id, update)
        _sync_summary_to_db(session_id, state)
        last_count = int(update.get("last_summarized_message_count") or 0)
        interview_db.set_last_summarized_message_count(session_id, last_count)
    record = interview_db.get_interview_by_session(session_id) or {}
    return (record.get("interview_summary") or state.get("running_summary") or "").strip()


def _require_active_interview(record: Dict[str, Any]) -> Dict[str, Any] | None:
    status = record.get("interview_status") or "active"
    if status == "paused":
        return {
            "status_code": 409,
            "error": "Interview is paused. Resume the interview to continue.",
            "interview_status": "paused",
        }
    if status == "completed" or record.get("interview_feedback"):
        return {
            "status_code": 409,
            "error": "Interview is already completed.",
            "interview_status": "completed",
        }
    return None


def _sync_summary_to_db(session_id: str, state: Dict[str, Any]) -> str:
    summary = (state.get("running_summary") or "").strip()
    if not session_id:
        return summary
    record = interview_db.get_interview_by_session(session_id)
    if not record:
        return summary
    existing = (record.get("interview_summary") or "").strip()
    if summary and summary != existing:
        interview_db.set_interview_summary(session_id, summary)
        logger.info("[interview_service] synced summary session_id=%s", session_id)
    return summary or existing


def _finalize_summary(session_id: str) -> str:
    """Run a final summarization pass before feedback."""
    from app.real_interview.backend.nodes.interview_nodes import maybe_summarize_node

    state = _get_merged_state(session_id)
    if not state:
        record = interview_db.get_interview_by_session(session_id)
        return (record or {}).get("interview_summary") or ""
    state["session_id"] = session_id
    update = maybe_summarize_node(state)
    if update:
        state.update(update)
        _sync_summary_to_db(session_id, state)
        last_count = int(update.get("last_summarized_message_count") or 0)
        interview_db.set_last_summarized_message_count(session_id, last_count)
    record = interview_db.get_interview_by_session(session_id)
    return (record or {}).get("interview_summary") or state.get("running_summary") or ""


def _persist_new_messages(session_id: str, state: Dict[str, Any], record: Dict[str, Any]) -> None:
    stored = record.get("messages") or []
    stored_count = len(stored)
    all_msgs = [_message_to_dict(m) for m in (state.get("messages") or [])]
    if len(all_msgs) > stored_count:
        interview_db.append_chat_messages(session_id, all_msgs[stored_count:])
        logger.info(
            "[interview_service] persisted %s new message(s) session_id=%s",
            len(all_msgs) - stored_count,
            session_id,
        )


def start_interview(
    *,
    customer_id: str,
    resume_id: str,
    job_application_id: str,
) -> Dict[str, Any]:
    session_id = make_thread_id(customer_id, resume_id, job_application_id)
    logger.info("[interview_service] start session_id=%s", session_id)

    state_preview = _get_merged_state(session_id)
    role = state_preview.get("job_role") or ""

    try:
        from app.real_interview.backend.services.interview_context_loader import load_interview_context

        ctx = load_interview_context(
            customer_id=customer_id,
            resume_id=resume_id,
            job_application_id=job_application_id,
        )
        role = ctx.get("job_role") or role
    except Exception:
        logger.exception("[interview_service] could not pre-load role for interview record")

    existing = interview_db.get_interview_by_session(session_id)
    if existing:
        _restore_checkpoint_if_missing(session_id)
        status = existing.get("interview_status") or "active"
        state = _get_merged_state(session_id)
        if state:
            state = _merge_summary_from_record(state, existing)
        if status == "paused":
            logger.info("[interview_service] start blocked: paused session_id=%s", session_id)
            return {
                "status_code": 409,
                "session_id": session_id,
                "interview_record_id": existing.get("interview_id"),
                "interview_status": "paused",
                "error": "Interview is paused. Use resume to continue.",
                "state": _public_state(state, existing) if state else _public_state({"session_id": session_id}, existing),
            }
        if status == "completed" or existing.get("interview_feedback"):
            return {
                "status_code": 409,
                "session_id": session_id,
                "error": "Interview already completed for this application.",
                "state": _public_state(state, existing) if state else None,
            }
        if state:
            logger.info("[interview_service] start: returning in-progress session_id=%s", session_id)
            return {
                "status_code": 200,
                "session_id": session_id,
                "interview_record_id": existing.get("interview_id"),
                "state": _public_state(state, existing),
                "message": "Interview already in progress.",
            }

    record_meta = interview_db.create_interview_record(
        session_id=session_id,
        candidate_id=customer_id,
        resume_id=resume_id,
        job_application_id=job_application_id,
        role_applied_for=role,
    )

    initial = {
        "customer_id": customer_id,
        "resume_id": resume_id,
        "job_application_id": job_application_id,
        "session_id": session_id,
        "interview_record_id": record_meta["interview_id"],
        "messages": [],
        "running_summary": "",
        "last_summarized_message_count": 0,
    }
    try:
        get_start_graph().invoke(initial, _config(session_id))
    except Exception as exc:
        logger.exception("[interview_service] start graph failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    state = _get_merged_state(session_id)
    state["session_id"] = session_id
    state["interview_record_id"] = record_meta["interview_id"]

    if state.get("error"):
        logger.warning("[interview_service] start completed with error: %s", state.get("error"))
        return {"status_code": 400, "error": state["error"], "session_id": session_id}

    record = interview_db.get_interview_by_session(session_id) or {}
    _persist_new_messages(session_id, state, record)
    _sync_summary_to_db(session_id, state)
    last_count = int(state.get("last_summarized_message_count") or 0)
    interview_db.set_last_summarized_message_count(session_id, last_count)

    record = interview_db.get_interview_by_session(session_id) or {}
    logger.info("[interview_service] start complete session_id=%s", session_id)
    return {
        "status_code": 200,
        "session_id": session_id,
        "interview_record_id": record_meta["interview_id"],
        "state": _public_state(state, record),
        "message": "Interview started. HR summary and panel are ready.",
    }


def send_interview_message(*, session_id: str, message: str, thread_id: str | None = None) -> Dict[str, Any]:
    if thread_id and not session_id:
        session_id = thread_id
    if not message or not message.strip():
        logger.warning("[interview_service] message rejected: empty body")
        return {"status_code": 400, "error": "message is required"}

    logger.info("[interview_service] message session_id=%s chars=%s", session_id, len(message))
    record = interview_db.get_interview_by_session(session_id)
    if not record:
        logger.warning("[interview_service] unknown session_id=%s", session_id)
        return {"status_code": 404, "error": "interview session not found", "session_id": session_id}

    _restore_checkpoint_if_missing(session_id)

    blocked = _require_active_interview(record)
    if blocked:
        blocked["session_id"] = session_id
        return blocked

    interview_db.append_chat_messages(
        session_id, [{"role": "user", "content": message.strip()}]
    )

    try:
        get_chat_graph().invoke(
            {"messages": [HumanMessage(content=message.strip())]},
            _config(session_id),
        )
    except Exception as exc:
        logger.exception("[interview_service] message graph failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    state = _get_merged_state(session_id)
    state["session_id"] = session_id

    record = interview_db.get_interview_by_session(session_id) or {}
    _persist_new_messages(session_id, state, record)

    _sync_summary_to_db(session_id, state)
    last_count = int(state.get("last_summarized_message_count") or 0)
    interview_db.set_last_summarized_message_count(session_id, last_count)

    if state.get("pending_auto_complete"):
        logger.info("[interview_service] auto-completing session_id=%s", session_id)
        return complete_interview(session_id=session_id)

    record = interview_db.get_interview_by_session(session_id) or {}
    return {
        "status_code": 200,
        "session_id": session_id,
        "state": _public_state(state, record),
    }


def advance_to_next_interviewer(*, session_id: str, thread_id: str | None = None) -> Dict[str, Any]:
    """Legacy endpoint — live panel interviews no longer use sequential handoffs."""
    if thread_id and not session_id:
        session_id = thread_id
    record = interview_db.get_interview_by_session(session_id)
    if not record:
        return {"status_code": 404, "error": "interview session not found", "session_id": session_id}
    state = _get_merged_state(session_id)
    return {
        "status_code": 409,
        "session_id": session_id,
        "error": "Panel interviews are continuous. Reply in chat — the panel will follow up based on your answer.",
        "state": _public_state(state, record) if state else _public_state({"session_id": session_id}, record),
    }


def complete_interview(
    *,
    session_id: str,
    thread_id: str | None = None,
    email_feedback: bool | None = None,
) -> Dict[str, Any]:
    if thread_id and not session_id:
        session_id = thread_id
    logger.info("[interview_service] complete session_id=%s", session_id)
    record = interview_db.get_interview_by_session(session_id)
    if not record:
        return {"status_code": 404, "error": "interview session not found", "session_id": session_id}

    _restore_checkpoint_if_missing(session_id)

    if (record.get("interview_status") or "active") == "paused":
        return {
            "status_code": 409,
            "error": "Interview is paused. Resume before ending.",
            "session_id": session_id,
        }

    try:
        summary = _finalize_summary(session_id)
        get_feedback_graph().invoke(
            {
                "running_summary": summary,
                "job_role": record.get("role_applied_for") or "",
            },
            _config(session_id),
        )
    except Exception as exc:
        logger.exception("[interview_service] complete failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    state = _get_merged_state(session_id)
    feedback = state.get("candidate_post_interview_feedback") or {}
    if feedback:
        interview_db.save_interview_feedback(session_id, feedback)
        interview_db.set_interview_status(session_id, "completed")
        logger.info(
            "[interview_service] feedback saved decision=%s",
            feedback.get("interview_decision"),
        )

    feedback_email_sent = False
    feedback_email_error = ""
    if feedback:
        sent, err = _maybe_send_feedback_email(
            session_id=session_id,
            record=record,
            feedback=feedback,
            email_feedback=email_feedback,
        )
        feedback_email_sent = sent
        feedback_email_error = err
        if sent:
            record = interview_db.get_interview_by_session(session_id) or {}

    message = "Interview feedback generated."
    if feedback_email_sent:
        message = "Interview feedback generated and emailed to your account address."
    elif feedback and _should_email_feedback(record, email_feedback=email_feedback) and feedback_email_error:
        message = "Interview feedback generated, but the email could not be sent."

    return {
        "status_code": 200,
        "session_id": session_id,
        "state": _public_state(state, record),
        "message": message,
        "feedback_email_sent": feedback_email_sent,
    }


def pause_interview(*, session_id: str, thread_id: str | None = None) -> Dict[str, Any]:
    if thread_id and not session_id:
        session_id = thread_id
    logger.info("[interview_service] pause session_id=%s", session_id)
    record = interview_db.get_interview_by_session(session_id)
    if not record:
        return {"status_code": 404, "error": "interview session not found", "session_id": session_id}

    _restore_checkpoint_if_missing(session_id)

    status = record.get("interview_status") or "active"
    if status == "paused":
        state = _get_merged_state(session_id)
        return {
            "status_code": 200,
            "session_id": session_id,
            "interview_status": "paused",
            "state": _public_state(state, record) if state else _public_state({"session_id": session_id}, record),
            "message": "Interview is already paused.",
        }
    if status == "completed" or record.get("interview_feedback"):
        return {"status_code": 409, "error": "Interview is already completed.", "session_id": session_id}

    try:
        summary = _force_summarize(session_id)
        interview_db.set_interview_status(session_id, "paused")
        _patch_checkpoint(
            session_id,
            {
                "running_summary": summary,
                "force_summarize": False,
            },
        )
    except Exception as exc:
        logger.exception("[interview_service] pause failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    record = interview_db.get_interview_by_session(session_id) or {}
    state = _get_merged_state(session_id)
    if state:
        state = _merge_summary_from_record(state, record)
    logger.info("[interview_service] paused session_id=%s summary_chars=%s", session_id, len(summary))
    return {
        "status_code": 200,
        "session_id": session_id,
        "interview_status": "paused",
        "state": _public_state(state, record) if state else _public_state({"session_id": session_id}, record),
        "message": "Interview paused. A summary was saved for when you resume.",
    }


def resume_interview(*, session_id: str, thread_id: str | None = None) -> Dict[str, Any]:
    if thread_id and not session_id:
        session_id = thread_id
    logger.info("[interview_service] resume session_id=%s", session_id)
    record = interview_db.get_interview_by_session(session_id)
    if not record:
        return {"status_code": 404, "error": "interview session not found", "session_id": session_id}

    _restore_checkpoint_if_missing(session_id)

    status = record.get("interview_status") or "active"
    if status != "paused":
        return {
            "status_code": 409,
            "error": "Interview is not paused.",
            "session_id": session_id,
            "interview_status": status,
        }

    summary = (record.get("interview_summary") or "").strip()
    last_count = int(record.get("last_summarized_message_count") or 0)
    try:
        interview_db.set_interview_status(session_id, "active")
        _patch_checkpoint(
            session_id,
            {
                "running_summary": summary,
                "last_summarized_message_count": last_count,
                "force_summarize": False,
            },
        )
    except Exception as exc:
        logger.exception("[interview_service] resume failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    record = interview_db.get_interview_by_session(session_id) or {}
    state = _get_merged_state(session_id)
    if state:
        state = _merge_summary_from_record(state, record)
    logger.info("[interview_service] resumed session_id=%s", session_id)
    return {
        "status_code": 200,
        "session_id": session_id,
        "interview_status": "active",
        "state": _public_state(state, record) if state else _public_state({"session_id": session_id}, record),
        "message": "Interview resumed. Your prior summary is available to the interviewers.",
    }


def list_user_interview_sessions(*, customer_id: str) -> Dict[str, Any]:
    """List paused or in-progress interviews for the signed-in user."""
    interviews = interview_db.list_open_interviews_for_candidate(customer_id)
    logger.info(
        "[interview_service] list_sessions customer_id=%s count=%s",
        customer_id,
        len(interviews),
    )
    return {
        "status_code": 200,
        "interviews": interviews,
        "count": len(interviews),
    }


def get_interview_state(*, session_id: str, thread_id: str | None = None) -> Dict[str, Any]:
    if thread_id and not session_id:
        session_id = thread_id
    logger.info("[interview_service] get_state session_id=%s", session_id)
    record = interview_db.get_interview_by_session(session_id)
    if record:
        _restore_checkpoint_if_missing(session_id)
    state = _get_merged_state(session_id)
    if not record and not state:
        return {"status_code": 404, "error": "interview session not found", "session_id": session_id}
    if state:
        state["session_id"] = session_id
    return {
        "status_code": 200,
        "session_id": session_id,
        "record": record,
        "state": _public_state(state, record) if state else None,
    }
