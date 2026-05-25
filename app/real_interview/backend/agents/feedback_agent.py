from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.real_interview import logger
from app.real_interview.backend.agents.interview_context import format_messages_for_summary
from app.real_interview.backend.config.configuration import get_feedback_config
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.real_interview.backend.state.interview_schemas import CandidatePostInterviewFeedback


class FeedbackAgent:
    """Post-interview feedback for the candidate (reads interview_summary from Mongo)."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        self._llm_wrapper = llm_wrapper or OpenAILLM()
        logger.info("[FeedbackAgent] initialized")

    def generate_feedback(
        self,
        *,
        interview_summary: str,
        role_applied_for: str = "",
        messages: Optional[List[BaseMessage]] = None,
        first_impression: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("[FeedbackAgent] generate_feedback summary_chars=%s", len(interview_summary or ""))
        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(CandidatePostInterviewFeedback)

        cfg = get_feedback_config()
        use_summary = bool(cfg.get("use_summary_primary", True))
        transcript = ""
        if messages and not use_summary:
            transcript = format_messages_for_summary(messages)

        system = SystemMessage(
            content=(
                "You provide constructive post-interview feedback to the candidate. "
                "Base your assessment primarily on the interview_summary. "
                "Set interview_decision to exactly one of: selected, not_selected, hold. "
                "Be professional and actionable in detailed_feedback."
            )
        )
        user = HumanMessage(
            content=(
                f"Role applied for: {role_applied_for or '(not specified)'}\n\n"
                f"Interview summary:\n{interview_summary or '(no summary)'}\n\n"
                f"HR pre-interview context:\n{first_impression or {}}\n\n"
                f"Additional transcript (if any):\n{transcript or '(not provided)'}"
            )
        )
        try:
            result: CandidatePostInterviewFeedback = structured.invoke([system, user])
            data = result.model_dump()
            logger.info("[FeedbackAgent] decision=%s", data.get("interview_decision"))
            return data
        except Exception:
            logger.exception("[FeedbackAgent] generate_feedback failed")
            return CandidatePostInterviewFeedback().model_dump()
