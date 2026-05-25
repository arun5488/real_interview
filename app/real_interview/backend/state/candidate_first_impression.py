from pydantic import BaseModel, Field


class CandidateFirstImpression(BaseModel):
    """HR recruiter output: candidate snapshot for the technical interview panel."""

    candidate_name: str = Field(default="", description="From parsed_data.name in resumes collection.")
    candidate_role: str = Field(
        default="",
        description="Most recent title from parsed_data.experience (newest role first).",
    )
    candidate_experience: str = Field(
        default="",
        description="Summary of total/relevant experience from parsed_data.experience.",
    )
    candidate_summary_pre_interview: str = Field(
        default="",
        description=(
            "150-200 word neutral or positive recruiter summary for the technical panel. "
            "Compare resume to job description only; do not invent facts."
        ),
    )
    experience_level: str = Field(
        default="",
        description="junior | mid | senior — inferred from resume vs job requirements.",
    )
