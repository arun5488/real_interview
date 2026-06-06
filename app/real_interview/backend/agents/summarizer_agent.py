import os
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.real_interview import logger
from app.real_interview.backend.agents.interview_context import format_messages_for_summary
from app.real_interview.backend.config.configuration import get_question_bank_config, get_summarizer_config
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.real_interview.backend.state.interview_schemas import QuestionBankExtract


class SummarizerAgent:
    """Neutral rolling summary of interview conversation (incremental, append-only)."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        self._llm_wrapper = llm_wrapper or OpenAILLM()
        logger.info("[SummarizerAgent] initialized")

    def summarize_increment(
        self,
        *,
        new_messages: List[BaseMessage],
        prior_summary: str = "",
    ) -> str:
        """Summarize only new messages; caller appends to stored summary."""
        logger.info("[SummarizerAgent] summarize_increment messages=%s", len(new_messages))
        if not new_messages:
            logger.info("[SummarizerAgent] no new messages; skipping")
            return ""

        cfg = get_summarizer_config()
        transcript = format_messages_for_summary(new_messages)
        max_chars = int(cfg.get("input_max_chars", 16000))
        transcript = transcript[:max_chars]

        llm = self._llm_wrapper.get_llm_model()
        system = SystemMessage(
            content=(
                "Summarize ONLY the new interview messages factually. "
                "Do not add opinions, judgments, or hiring recommendations. "
                "Do not repeat the prior summary; produce a short incremental segment."
            )
        )
        user = HumanMessage(
            content=(
                f"Prior summary (for context only, do not copy):\n{prior_summary or '(none)'}\n\n"
                f"New messages to summarize:\n{transcript}\n\n"
                "Produce a concise incremental summary segment."
            )
        )
        try:
            result = llm.invoke([system, user])
            segment = (result.content or "").strip()
            logger.info("[SummarizerAgent] produced segment chars=%s", len(segment))
            return segment
        except Exception:
            logger.exception("[SummarizerAgent] summarize_increment failed")
            return ""

    def summarize(
        self,
        *,
        messages: List[BaseMessage],
        prior_summary: str = "",
    ) -> str:
        """Backward-compatible wrapper."""
        _ = os.environ  # keep module import pattern stable
        return self.summarize_increment(new_messages=messages, prior_summary=prior_summary)

    def extract_questions_for_bank(
        self,
        *,
        new_messages: List[BaseMessage],
        job_role: str,
        experience_level: str,
    ) -> list[dict[str, str]]:
        """
        Identify new interview questions asked by interviewers in recent messages.
        Returns dicts suitable for question_bank.append_questions_to_bank.
        """
        logger.info(
            "[SummarizerAgent] extract_questions_for_bank role=%s level=%s messages=%s",
            job_role,
            experience_level,
            len(new_messages),
        )
        if not new_messages or not (job_role or "").strip():
            return []

        cfg = get_question_bank_config()
        transcript = format_messages_for_summary(new_messages)
        max_chars = int(cfg.get("extract_max_chars", 12000))
        transcript = transcript[:max_chars]
        if not transcript.strip():
            return []

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(QuestionBankExtract)
        system = SystemMessage(
            content=(
                "Extract technical interview QUESTIONS that interviewers asked in the transcript. "
                "Return only clear, reusable question sentences (not candidate answers). "
                "Deduplicate similar questions. Skip greetings and filler. "
                "Assign topic when obvious (apis, databases, system design, behavioral, etc.). "
                "Set interviewer_style to positive, negative, or objective only when clearly evident; "
                "otherwise leave it empty."
            )
        )
        user = HumanMessage(
            content=(
                f"Job role: {job_role}\n"
                f"Experience level: {experience_level}\n\n"
                f"Transcript:\n{transcript}\n\n"
                "List new interview questions to save in the question bank."
            )
        )
        try:
            result: QuestionBankExtract = structured.invoke([system, user])
            out = []
            for item in result.questions:
                text = (item.text or "").strip()
                if len(text) >= 12:
                    out.append(
                        {
                            "text": text,
                            "topic": (item.topic or "").strip(),
                            "interviewer_style": (item.interviewer_style or "").strip().lower(),
                        }
                    )
            logger.info("[SummarizerAgent] extracted %s question(s) for bank", len(out))
            return out
        except Exception:
            logger.exception("[SummarizerAgent] extract_questions_for_bank failed")
            return []
