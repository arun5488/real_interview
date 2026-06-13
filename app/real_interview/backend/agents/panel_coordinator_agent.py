from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.real_interview import logger
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.real_interview.backend.state.interview_schemas import PanelResponsePlan


def _panel_roster(selected: List[str]) -> str:
    lines = []
    for i, style in enumerate(selected):
        lines.append(f"I{i + 1}: {style}")
    return "\n".join(lines)


def _last_human_text(messages: List[BaseMessage]) -> str:
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "human" or msg.__class__.__name__ == "HumanMessage":
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


class PanelCoordinatorAgent:
    """Chooses which panel members speak next in a live group interview."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        self._llm_wrapper = llm_wrapper or OpenAILLM()

    def _clamp_indices(self, indices: List[int], panel_size: int) -> List[int]:
        seen: set[int] = set()
        out: List[int] = []
        for raw in indices:
            idx = int(raw)
            if idx < 0 or idx >= panel_size or idx in seen:
                continue
            seen.add(idx)
            out.append(idx)
            if len(out) >= 2:
                break
        return out

    def _fallback_opening(self, panel_size: int) -> List[int]:
        if panel_size >= 2:
            return [0, 1]
        return [0]

    def _fallback_follow_up(self, panel_size: int, messages: List[BaseMessage]) -> List[int]:
        if panel_size < 2:
            return [0]
        assistant_count = sum(
            1
            for m in messages
            if getattr(m, "type", "") == "ai" or m.__class__.__name__ == "AIMessage"
        )
        return [assistant_count % panel_size]

    def plan_opening(self, panel_plan: Dict[str, Any]) -> List[int]:
        selected = panel_plan.get("selected_interviewers") or []
        panel_size = len(selected)
        if panel_size == 0:
            return [0]
        if panel_size == 1:
            return [0]

        llm = self._llm_wrapper.get_llm_model().with_structured_output(PanelResponsePlan)
        system = SystemMessage(
            content=(
                "You coordinate a live panel interview. All interviewers are in the room at the same time.\n"
                "For the opening, pick 1–2 panel members who should speak first.\n"
                "Usually one lead welcomes the candidate and asks the first question; a second panelist "
                "may briefly introduce themselves and add one complementary opening question.\n"
                "Return speaker_indices as 0-based indices into the panel roster."
            )
        )
        user = HumanMessage(
            content=(
                f"Panel roster:\n{_panel_roster(selected)}\n\n"
                f"Experience level: {panel_plan.get('experience_level') or 'unknown'}\n"
                f"Routing note: {panel_plan.get('routing_rationale') or ''}\n\n"
                "Who should speak at the opening?"
            )
        )
        try:
            plan: PanelResponsePlan = llm.invoke([system, user])
            indices = self._clamp_indices(plan.speaker_indices, panel_size)
            if indices:
                logger.info("[PanelCoordinator] opening speakers=%s", indices)
                return indices
        except Exception:
            logger.exception("[PanelCoordinator] opening plan failed; using fallback")
        return self._fallback_opening(panel_size)

    def plan_follow_up(
        self,
        *,
        panel_plan: Dict[str, Any],
        messages: List[BaseMessage],
        running_summary: str = "",
    ) -> List[int]:
        selected = panel_plan.get("selected_interviewers") or []
        panel_size = len(selected)
        if panel_size == 0:
            return [0]
        if panel_size == 1:
            return [0]

        last_answer = _last_human_text(messages)
        llm = self._llm_wrapper.get_llm_model().with_structured_output(PanelResponsePlan)
        system = SystemMessage(
            content=(
                "You coordinate a live panel interview. All interviewers are present and hear every answer.\n"
                "After each candidate answer, choose 1–2 panel members who should ask the next follow-up.\n"
                "Base questions on what the candidate just said — probe gaps, trade-offs, or depth.\n"
                "Rotate speakers; avoid the same person dominating unless their style fits the topic.\n"
                "Return speaker_indices as 0-based indices (max 2)."
            )
        )
        summary_block = ""
        if (running_summary or "").strip():
            summary_block = f"\n\nEarlier interview summary:\n{running_summary.strip()}"

        user = HumanMessage(
            content=(
                f"Panel roster:\n{_panel_roster(selected)}\n"
                f"{summary_block}\n\n"
                f"Candidate's latest answer:\n{last_answer or '(none)'}\n\n"
                "Which panel member(s) should respond next?"
            )
        )
        try:
            plan: PanelResponsePlan = llm.invoke([system, user])
            indices = self._clamp_indices(plan.speaker_indices, panel_size)
            if indices:
                logger.info("[PanelCoordinator] follow-up speakers=%s", indices)
                return indices
        except Exception:
            logger.exception("[PanelCoordinator] follow-up plan failed; using fallback")
        return self._fallback_follow_up(panel_size, messages)
