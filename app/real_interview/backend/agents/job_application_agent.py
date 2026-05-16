import os
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.real_interview import logger
from app.real_interview.backend.llm.openaillm import OpenAILLM


class JobApplicationExtractionModel(BaseModel):
    """Structured job posting fields for storage and downstream agents."""

    job_role: str = Field(
        default="",
        description="Primary role or job title the candidate is applying for",
    )
    job_description: str = Field(
        default="",
        description=(
            "Agent-readable job description: clear sections (role, company if known, "
            "responsibilities, requirements, location, compensation if stated). Use plain text."
        ),
    )


class JobApplicationAgent:
    """Uses the same OpenAI stack as resume parsing to normalize job postings."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        logger.info("[JobApplicationAgent] init")
        self._llm_wrapper = llm_wrapper or OpenAILLM()

    def extract_from_text(
        self,
        raw_text: str,
        *,
        source: str = "description",
        application_link: Optional[str] = None,
    ) -> Dict[str, str]:
        logger.info("[JobApplicationAgent] extract_from_text source=%s", source)
        if not raw_text or not raw_text.strip():
            return {"job_role": "", "job_description": ""}

        max_chars = int(os.getenv("JOB_APPLICATION_MAX_CHARS", "16000").strip() or "16000")
        snippet = raw_text.strip()[:max_chars]
        if len(raw_text.strip()) > max_chars:
            snippet += "\n\n[... text truncated for parsing ...]"

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(JobApplicationExtractionModel)

        link_note = ""
        if application_link:
            link_note = f"\nThe posting was loaded from this URL: {application_link}\n"

        system = SystemMessage(
            content=(
                "You extract job application data from job posting text (web page text or user paste). "
                "Set job_role to the primary position title. "
                "Set job_description to a clean, agent-readable summary using labeled sections "
                "(Role, Company, Location, Responsibilities, Requirements, Nice-to-have, Compensation). "
                "Use only information present in the text. Do not invent employers or requirements."
            )
        )
        user = HumanMessage(
            content=(
                f"Source type: {source}.{link_note}\n"
                "Extract job_role and job_description from the following text.\n\n"
                f"{snippet}"
            )
        )

        try:
            parsed: JobApplicationExtractionModel = structured.invoke([system, user])
            data = parsed.model_dump()
            return {
                "job_role": (data.get("job_role") or "").strip(),
                "job_description": (data.get("job_description") or "").strip(),
            }
        except Exception:
            logger.exception("[JobApplicationAgent] LLM extraction failed")
            return {"job_role": "", "job_description": snippet[:8000]}
