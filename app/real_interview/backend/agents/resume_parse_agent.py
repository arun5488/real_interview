import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.real_interview import logger
from app.real_interview.backend.llm.openaillm import OpenAILLM


class EducationItem(BaseModel):
    """One education entry from a resume."""

    institution: str = Field(default="", description="School or university name")
    degree: str = Field(default="", description="Degree or qualification")
    field: str = Field(default="", description="Major or field of study")
    dates: str = Field(default="", description="Time range if visible")


class ExperienceItem(BaseModel):
    """One work experience entry from a resume."""

    company: str = Field(default="", description="Employer name")
    title: str = Field(default="", description="Job title")
    dates: str = Field(default="", description="Employment dates")
    description: str = Field(default="", description="Summary or bullet content")


class ResumeParsedDataModel(BaseModel):
    """Structured resume fields aligned with the `resume` collection `parsed_data` object."""

    name: str = Field(default="", description="Full name")
    email: str = Field(default="", description="Primary email")
    phone: str = Field(default="", description="Primary phone")
    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class ResumeParseAgent:
    """Uses the configured OpenAI chat model to turn resume text into structured `parsed_data`."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        logger.info("inside __init__")
        self._llm_wrapper = llm_wrapper or OpenAILLM()

    def populate_parsed_data(self, raw_text: str) -> Dict[str, Any]:
        logger.info("inside populate_parsed_data")
        if not raw_text or not raw_text.strip():
            return self._empty_parsed_data()

        max_chars = int(os.getenv("RESUME_PARSE_MAX_CHARS", "14000").strip() or "14000")
        snippet = raw_text.strip()[:max_chars]
        if len(raw_text.strip()) > max_chars:
            snippet += "\n\n[... text truncated for parsing ...]"

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(ResumeParsedDataModel)

        system = SystemMessage(
            content=(
                "You extract structured data from resume or CV plain text. "
                "Use only information that appears in the text. "
                "If a field is missing, use an empty string or empty list. "
                "Do not invent employers, degrees, or certifications."
            )
        )
        user = HumanMessage(
            content=(
                "Extract structured resume data from the following text.\n\n"
                f"{snippet}"
            )
        )

        try:
            parsed: ResumeParsedDataModel = structured.invoke([system, user])
            return parsed.model_dump()
        except Exception:
            logger.exception("[ResumeParseAgent] LLM structured parse failed; returning empty shape")
            return self._empty_parsed_data()

    @staticmethod
    def _empty_parsed_data() -> Dict[str, Any]:
        logger.info("inside _empty_parsed_data")
        return {
            "name": "",
            "email": "",
            "phone": "",
            "education": [],
            "experience": [],
            "skills": [],
            "certifications": [],
        }
