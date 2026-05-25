import random
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.real_interview import logger
from app.real_interview.backend.agents.interview_context import format_first_impression
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.real_interview.backend.state.interview_schemas import INTERVIEWER_TYPES, InterviewPanelPlan


class RouterAgent:
    """Orchestrator: reads first impression and builds the interview panel."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        logger.info("[RouterAgent] initialized")
        self._llm_wrapper = llm_wrapper or OpenAILLM()

    def build_panel_plan(self, first_impression: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[RouterAgent] build_panel_plan start")
        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(InterviewPanelPlan)

        system = SystemMessage(
            content=(
                "You orchestrate the interview process. Read the candidate first impression summary.\n"
                "Decide panel_size: use 1 interviewer if the candidate is less experienced (junior), "
                "use 2 interviewers if more experienced (mid or senior).\n"
                "Do NOT list interviewer names in selected_interviewers — that is assigned separately.\n"
                "Return experience_level and panel_size (1 or 2) and routing_rationale only; "
                "leave selected_interviewers as an empty list."
            )
        )
        user = HumanMessage(
            content=(
                "Candidate first impression:\n"
                f"{format_first_impression(first_impression)}"
            )
        )

        try:
            plan: InterviewPanelPlan = structured.invoke([system, user])
            data = plan.model_dump()
        except Exception:
            logger.exception("[RouterAgent] LLM failed; using defaults")
            data = InterviewPanelPlan().model_dump()

        panel_size = int(data.get("panel_size") or 1)
        panel_size = 1 if panel_size < 2 else 2
        level = (data.get("experience_level") or first_impression.get("experience_level") or "").lower()
        if not level:
            level = "junior" if panel_size == 1 else "senior"
        if level == "junior":
            panel_size = 1
        elif level in ("mid", "senior"):
            panel_size = 2

        pool: List[str] = list(INTERVIEWER_TYPES)
        selected = random.sample(pool, panel_size)
        data["panel_size"] = panel_size
        data["selected_interviewers"] = selected
        data["experience_level"] = level
        logger.info("[RouterAgent] panel=%s interviewers=%s", panel_size, selected)
        return data
