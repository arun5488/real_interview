import os
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.real_interview import logger
from app.real_interview.backend.agents.interview_context import format_parsed_resume
from app.real_interview.backend.llm.openaillm import OpenAILLM
from app.real_interview.backend.state.candidate_first_impression import CandidateFirstImpression


class HrRecruiterAgent:
    """Senior recruiter: resume vs job description → first impression for the technical panel."""

    def __init__(self, llm_wrapper: Optional[OpenAILLM] = None) -> None:
        logger.info("[HrRecruiterAgent] initialized")
        self._llm_wrapper = llm_wrapper or OpenAILLM()

    def analyze(
        self,
        *,
        parsed_data: Dict[str, Any],
        job_role: str,
        job_description: str,
    ) -> Dict[str, Any]:
        logger.info("[HrRecruiterAgent] analyze start")
        resume_text = format_parsed_resume(parsed_data)
        max_job = int(os.getenv("INTERVIEW_JOB_DESC_MAX_CHARS", "12000").strip() or "12000")
        job_snippet = (job_description or "")[:max_job]

        llm = self._llm_wrapper.get_llm_model()
        structured = llm.with_structured_output(CandidateFirstImpression)

        system = SystemMessage(
            content=(
                "You are a Senior Recruiter at your firm. Evaluate the candidate using ONLY the resume "
                "and job description provided. Do not assume or invent facts.\n"
                "Fill candidate_name from resume name; candidate_role from the most recent experience title; "
                "candidate_experience as a concise experience summary.\n"
                "candidate_summary_pre_interview must be 150-200 words only, neutral or positive in tone, "
                "for the technical interview panel.\n"
                "experience_level must be one of: junior, mid, senior — based on fit of resume to role."
            )
        )
        user = HumanMessage(
            content=(
                f"Target job role: {job_role or '(not specified)'}\n\n"
                f"Job description:\n{job_snippet}\n\n"
                f"Resume (parsed_data):\n{resume_text}"
            )
        )

        try:
            result: CandidateFirstImpression = structured.invoke([system, user])
            data = result.model_dump()
            summary = (data.get("candidate_summary_pre_interview") or "").strip()
            words = len(summary.split())
            if words > 220:
                data["candidate_summary_pre_interview"] = " ".join(summary.split()[:200])
            return data
        except Exception:
            logger.exception("[HrRecruiterAgent] failed")
            return CandidateFirstImpression().model_dump()
