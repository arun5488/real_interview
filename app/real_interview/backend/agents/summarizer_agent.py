import os
from typing import List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.real_interview import logger
from app.real_interview.backend.agents.interview_context import format_messages_for_summary
from app.real_interview.backend.config.configuration import get_summarizer_config
from app.real_interview.backend.llm.openaillm import OpenAILLM


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
