import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.real_interview import logger
from app.real_interview.backend.agents.interview_context import format_first_impression, format_parsed_resume
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.real_interview.backend.tools.tavily_search import get_interviewer_tools

INTERVIEWER_PROMPTS = {
    "positive": (
        "You are a very experienced technical interviewer for the role of {candidate_role}. "
        "You are very positive in nature. After evaluating the candidate's resume and HR summary, "
        "test knowledge starting from basics. Questions must reflect the candidate's experience; "
        "probe further based on their answers. Analyze answers positively; be motivating. "
        "When the candidate indicates the interview is ending, state clearly whether you would "
        "select them and why."
    ),
    "negative": (
        "You are a very experienced technical interviewer for the role of {candidate_role}. "
        "You are very negative in nature. After evaluating the resume and HR summary, "
        "test from basics based on experience; probe on answers. Analyze answers critically; "
        "your tone is challenging. When the interview ends, state clearly whether you would select them."
    ),
    "objective": (
        "You are a very experienced technical interviewer for the role of {candidate_role}. "
        "You are objective and process-oriented. Ask many process-oriented questions grounded in "
        "the candidate's background and the role. When the interview ends, state clearly whether "
        "you would select them."
    ),
}


class InterviewerAgent:
    """Technical interviewer with optional Tavily search."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        logger.info("[InterviewerAgent] initialized")
        self._llm_wrapper = llm_wrapper or OpenAILLM()
        self._tools = get_interviewer_tools()
        self._tools_by_name = {t.name: t for t in self._tools}

    def _system_prompt(self, interviewer_type: str, candidate_role: str) -> str:
        template = INTERVIEWER_PROMPTS.get(interviewer_type, INTERVIEWER_PROMPTS["objective"])
        base = template.format(candidate_role=candidate_role or "the position")
        return (
            f"{base}\n\n"
            "Prefer curated question-bank seeds when provided; personalize them to this candidate's resume. "
            "Use tavily_web_search only when you need fresh technical facts or to probe deeper after a weak answer — "
            "not to fetch generic interview question lists.\n"
            "Stay in character for your interviewer style."
        )

    def _question_bank_context(self, seeds: List[Dict[str, Any]], interviewer_type: str) -> str:
        if not seeds:
            return (
                "\n\nNo curated question bank exists yet for this role and level. "
                "Generate appropriate questions from the resume, job description, and HR summary."
            )
        lines = []
        for i, item in enumerate(seeds, 1):
            text = (item.get("text") or "").strip()
            if not text:
                continue
            topic = (item.get("topic") or "").strip()
            suffix = f" (topic: {topic})" if topic else ""
            lines.append(f"{i}. {text}{suffix}")
        if not lines:
            return (
                "\n\nNo unused question-bank seeds remain; continue based on the conversation and resume."
            )
        return (
            "\n\nCurated question bank (prefer these; personalize; do not repeat questions already answered):\n"
            + "\n".join(lines)
        )

    def _summary_context(self, interview_summary: str) -> str:
        summary = (interview_summary or "").strip()
        if not summary:
            return ""
        return (
            "\n\nInterview progress summary (use as context; interview may have been paused and resumed):\n"
            + summary
        )

    def run_turn(
        self,
        *,
        interviewer_type: str,
        candidate_role: str,
        parsed_data: Dict[str, Any],
        first_impression: Dict[str, Any],
        messages: List[BaseMessage],
        interview_summary: str = "",
        question_bank_seeds: Optional[List[Dict[str, Any]]] = None,
    ) -> AIMessage:
        logger.info("[InterviewerAgent] run_turn type=%s", interviewer_type)
        llm = self._llm_wrapper.get_llm_model().bind_tools(self._tools)
        max_tool_rounds = int(os.getenv("INTERVIEWER_MAX_TOOL_ROUNDS", "3").strip() or "3")

        system = SystemMessage(
            content=(
                self._system_prompt(interviewer_type, candidate_role)
                + "\n\nResume:\n"
                + format_parsed_resume(parsed_data)
                + "\n\nHR summary:\n"
                + format_first_impression(first_impression)
                + self._summary_context(interview_summary)
                + self._question_bank_context(question_bank_seeds or [], interviewer_type)
            )
        )
        convo: List[BaseMessage] = [system] + list(messages)

        for _ in range(max_tool_rounds):
            response = llm.invoke(convo)
            if not getattr(response, "tool_calls", None):
                return response if isinstance(response, AIMessage) else AIMessage(content=str(response.content))

            convo.append(response)
            for call in response.tool_calls:
                name = call.get("name") if isinstance(call, dict) else call["name"]
                args = call.get("args") if isinstance(call, dict) else call["args"]
                tool = self._tools_by_name.get(name)
                if tool:
                    try:
                        result = tool.invoke(args)
                    except Exception as exc:
                        result = f"Tool error: {exc}"
                else:
                    result = f"Unknown tool: {name}"
                convo.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=call.get("id") if isinstance(call, dict) else call["id"],
                    )
                )

        final = llm.invoke(convo)
        return final if isinstance(final, AIMessage) else AIMessage(content=str(final.content))

    def opening_message(
        self,
        *,
        interviewer_type: str,
        candidate_role: str,
        parsed_data: Dict[str, Any],
        first_impression: Dict[str, Any],
        interview_summary: str = "",
        question_bank_seeds: Optional[List[Dict[str, Any]]] = None,
    ) -> AIMessage:
        prompt = HumanMessage(
            content=(
                "Start the interview. Introduce yourself briefly in character, "
                "then ask your first question. Prefer an unused question-bank seed if available; "
                "otherwise base it on the resume and HR summary."
            )
        )
        return self.run_turn(
            interviewer_type=interviewer_type,
            candidate_role=candidate_role,
            parsed_data=parsed_data,
            first_impression=first_impression,
            messages=[prompt],
            interview_summary=interview_summary,
            question_bank_seeds=question_bank_seeds,
        )
