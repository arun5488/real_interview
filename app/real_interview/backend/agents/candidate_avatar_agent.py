import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.real_interview import logger
from app.real_interview.backend.agents.interview_context import format_parsed_resume
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.real_interview.backend.state.interview_schemas import AvatarDiscussResponse, IdealAnswersReport
from app.real_interview.backend.tools.tavily_search import get_interviewer_tools


class CandidateAvatarAgent:
    """
    Builds an ideal candidate persona from the resume and drafts stronger answers
    to each technical interview question (report-only; not used in live chat).
    """

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        self._llm_wrapper = llm_wrapper or OpenAILLM()
        self._tools = get_interviewer_tools()
        self._tools_by_name = {t.name: t for t in self._tools}
        logger.info("[CandidateAvatarAgent] initialized")

    def _format_qa_block(self, qa_pairs: List[Dict[str, str]]) -> str:
        lines: List[str] = []
        for idx, item in enumerate(qa_pairs, start=1):
            interviewer = item.get("interviewer") or "I?"
            question = (item.get("question") or "").strip()
            answer = (item.get("candidate_answer") or "").strip()
            lines.append(f"{idx}. [{interviewer}] Question: {question}")
            lines.append(f"   Candidate answered: {answer}")
        return "\n".join(lines)

    def _run_tool_research(
        self,
        *,
        parsed_data: Dict[str, Any],
        job_role: str,
        job_description: str,
        qa_pairs: List[Dict[str, str]],
        interview_summary: str,
    ) -> str:
        llm = self._llm_wrapper.get_llm_model().bind_tools(self._tools)
        max_rounds = int(os.getenv("AVATAR_MAX_TOOL_ROUNDS", "4").strip() or "4")

        system = SystemMessage(
            content=(
                "You are researching context to help craft ideal interview answers for a candidate. "
                "Use tavily_web_search when factual, up-to-date, or role-specific details would improve "
                "an answer beyond what is in the resume. Search only when needed — not for every question. "
                "Summarize useful findings; note source URLs when available."
            )
        )
        user = HumanMessage(
            content=(
                f"Role: {job_role or '(not specified)'}\n\n"
                f"Job description:\n{(job_description or '(not provided)')[:8000]}\n\n"
                f"Resume:\n{format_parsed_resume(parsed_data)}\n\n"
                f"Interview summary:\n{(interview_summary or '(none)')[:6000]}\n\n"
                f"Questions and candidate answers:\n{self._format_qa_block(qa_pairs)}\n\n"
                "Search the web for gaps where the candidate's answer was weak or missing context. "
                "Return a concise research brief with URLs for anything you looked up."
            )
        )
        convo: List[BaseMessage] = [system, user]

        for _ in range(max_rounds):
            response = llm.invoke(convo)
            if not getattr(response, "tool_calls", None):
                return response.content if isinstance(response.content, str) else str(response.content)

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

        last = convo[-1]
        if isinstance(last, AIMessage):
            return last.content if isinstance(last.content, str) else str(last.content)
        return ""

    def generate_ideal_answers(
        self,
        *,
        parsed_data: Dict[str, Any],
        job_role: str,
        job_description: str,
        qa_pairs: List[Dict[str, str]],
        interview_summary: str = "",
    ) -> Dict[str, Any]:
        if not qa_pairs:
            logger.info("[CandidateAvatarAgent] no Q&A pairs; skipping")
            return IdealAnswersReport(
                avatar_summary="No technical Q&A pairs were found in this interview.",
                items=[],
            ).model_dump()

        logger.info("[CandidateAvatarAgent] generating for %s Q&A pair(s)", len(qa_pairs))
        research = self._run_tool_research(
            parsed_data=parsed_data,
            job_role=job_role,
            job_description=job_description,
            qa_pairs=qa_pairs,
            interview_summary=interview_summary,
        )

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(IdealAnswersReport)

        system = SystemMessage(
            content=(
                "You embody the IDEAL version of this candidate — grounded strictly in their resume, "
                "experience, and stated skills. Speak in first person as the candidate. "
                "For each interviewer question, write the best answer they could give: specific, structured, "
                "honest about limits, and aligned with their real background (do not invent employers or degrees). "
                "When web research was used, weave in accurate context and list each source in web_sources with title and url. "
                "Improve on weak or vague actual answers while staying authentic to this person."
            )
        )
        user = HumanMessage(
            content=(
                f"Role applied for: {job_role or '(not specified)'}\n\n"
                f"Job description:\n{(job_description or '(not provided)')[:8000]}\n\n"
                f"Candidate resume (parsed):\n{format_parsed_resume(parsed_data)}\n\n"
                f"Interview summary:\n{(interview_summary or '(none)')[:6000]}\n\n"
                f"Web research brief:\n{research or '(none)'}\n\n"
                f"Q&A to improve:\n{self._format_qa_block(qa_pairs)}\n\n"
                "Return one ideal_answer per numbered question. Include web_sources only when a URL was used."
            )
        )

        try:
            result: IdealAnswersReport = structured.invoke([system, user])
            data = result.model_dump()
            logger.info("[CandidateAvatarAgent] produced %s ideal answer(s)", len(data.get("items") or []))
            return data
        except Exception:
            logger.exception("[CandidateAvatarAgent] generate_ideal_answers failed")
            return IdealAnswersReport(
                avatar_summary="Ideal answers could not be generated for this session.",
                items=[],
            ).model_dump()

    def _format_chat_history(self, history: List[Dict[str, str]]) -> str:
        lines: List[str] = []
        for item in history or []:
            role = (item.get("role") or "").strip().lower()
            content = (item.get("content") or "").strip()
            if not content:
                continue
            label = "Candidate question" if role == "user" else "Ideal avatar"
            lines.append(f"{label}: {content}")
        return "\n".join(lines)[-8000:]

    def _run_tool_research_for_question(
        self,
        *,
        parsed_data: Dict[str, Any],
        job_role: str,
        question: str,
    ) -> str:
        llm = self._llm_wrapper.get_llm_model().bind_tools(self._tools)
        max_rounds = int(os.getenv("AVATAR_MAX_TOOL_ROUNDS", "4").strip() or "4")

        system = SystemMessage(
            content=(
                "You research factual context to help craft an ideal interview answer. "
                "Use tavily_web_search when up-to-date or technical facts would improve the answer. "
                "Return a brief research note with source URLs when you search."
            )
        )
        user = HumanMessage(
            content=(
                f"Target role: {job_role or '(general)'}\n\n"
                f"Resume:\n{format_parsed_resume(parsed_data)}\n\n"
                f"Interview question to answer:\n{question}\n\n"
                "Search only if it materially improves the answer."
            )
        )
        convo: List[BaseMessage] = [system, user]

        for _ in range(max_rounds):
            response = llm.invoke(convo)
            if not getattr(response, "tool_calls", None):
                return response.content if isinstance(response.content, str) else str(response.content)

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

        last = convo[-1]
        if isinstance(last, AIMessage):
            return last.content if isinstance(last.content, str) else str(last.content)
        return ""

    def answer_interview_question(
        self,
        *,
        parsed_data: Dict[str, Any],
        job_role: str = "",
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Ideal first-person answer for a single interview question (Discuss with Avatar)."""
        question = (question or "").strip()
        if not question:
            return AvatarDiscussResponse(
                ideal_answer="Please ask an interview question.",
                web_sources=[],
            ).model_dump()

        logger.info("[CandidateAvatarAgent] discuss question chars=%s", len(question))
        research = self._run_tool_research_for_question(
            parsed_data=parsed_data,
            job_role=job_role,
            question=question,
        )

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(AvatarDiscussResponse)

        history_block = self._format_chat_history(history or [])
        system = SystemMessage(
            content=(
                "You are the IDEAL avatar of this candidate — grounded in their resume and experience. "
                "The user asks interview questions; you respond with the best answer they could give in an interview. "
                "Use first person, be specific and structured, stay honest about limits, and do not invent employers or degrees. "
                "When web research was used, weave in accurate context and list sources in web_sources with title and url."
            )
        )
        user = HumanMessage(
            content=(
                f"Target role: {job_role or '(general interview practice)'}\n\n"
                f"Resume:\n{format_parsed_resume(parsed_data)}\n\n"
                f"Web research:\n{research or '(none)'}\n\n"
                f"Prior conversation:\n{history_block or '(none)'}\n\n"
                f"New interview question:\n{question}"
            )
        )

        try:
            result: AvatarDiscussResponse = structured.invoke([system, user])
            data = result.model_dump()
            logger.info("[CandidateAvatarAgent] discuss answer chars=%s", len(data.get("ideal_answer") or ""))
            return data
        except Exception:
            logger.exception("[CandidateAvatarAgent] answer_interview_question failed")
            return AvatarDiscussResponse(
                ideal_answer="I could not generate an answer right now. Please try again.",
                web_sources=[],
            ).model_dump()
