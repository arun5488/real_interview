from typing import List, Literal

from pydantic import BaseModel, Field

InterviewerType = Literal["positive", "negative", "objective"]

INTERVIEWER_TYPES: tuple[str, ...] = ("positive", "negative", "objective")


class InterviewPanelPlan(BaseModel):
    """Router output: who interviews the candidate."""

    experience_level: str = Field(default="", description="junior | mid | senior")
    panel_size: int = Field(default=1, description="1 for less experienced, 2 for more experienced.")
    selected_interviewers: List[InterviewerType] = Field(
        default_factory=list,
        description="Subset of positive, negative, objective.",
    )
    routing_rationale: str = Field(default="")


class InterviewerTurnResult(BaseModel):
    """Optional structured metadata for an interviewer turn."""

    interviewer_type: str = Field(default="")
    selects_candidate: bool = Field(default=False)
    conclusion: str = Field(default="")


class CandidatePostInterviewFeedback(BaseModel):
    """Feedback agent output for the candidate."""

    overall_assessment: str = Field(default="")
    strengths: List[str] = Field(default_factory=list)
    areas_to_improve: List[str] = Field(default_factory=list)
    recommendation: str = Field(default="")
    interview_decision: str = Field(
        default="",
        description="Final decision: selected, not_selected, or hold.",
    )
    detailed_feedback: str = Field(default="")
