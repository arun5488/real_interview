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


class PanelResponsePlan(BaseModel):
    """Panel coordinator: which interviewers speak next (live panel)."""

    speaker_indices: List[int] = Field(
        default_factory=list,
        description="0-based indices into selected_interviewers; 1–2 speakers per turn.",
    )
    rationale: str = Field(default="")


class InterviewerTurnResult(BaseModel):
    """Optional structured metadata for an interviewer turn."""

    interviewer_type: str = Field(default="")
    selects_candidate: bool = Field(default=False)
    conclusion: str = Field(default="")


class BankQuestionItem(BaseModel):
    """A single interview question stored in the question bank."""

    text: str = Field(description="Interview question text")
    topic: str = Field(default="", description="e.g. apis, system design, databases")
    interviewer_style: str = Field(
        default="",
        description="positive, negative, objective, or empty for any style",
    )


class QuestionBankExtract(BaseModel):
    """Summarizer output: new questions to append to the bank."""

    questions: List[BankQuestionItem] = Field(default_factory=list)


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


class IdealAnswerWebSource(BaseModel):
    """Web reference cited in an ideal answer."""

    title: str = Field(default="")
    url: str = Field(default="")


class IdealAnswerItem(BaseModel):
    """Ideal response for one interviewer question."""

    interviewer: str = Field(default="", description="Panel label e.g. I1")
    question: str = Field(default="")
    candidate_answer: str = Field(default="")
    ideal_answer: str = Field(default="")
    web_sources: List[IdealAnswerWebSource] = Field(default_factory=list)


class IdealAnswersReport(BaseModel):
    """Avatar agent output: best answers grounded in the candidate resume."""

    avatar_summary: str = Field(
        default="",
        description="How the ideal candidate persona was derived from the resume.",
    )
    items: List[IdealAnswerItem] = Field(default_factory=list)


class AvatarDiscussResponse(BaseModel):
    """Single-turn ideal answer for Discuss with Avatar chat."""

    ideal_answer: str = Field(default="")
    web_sources: List[IdealAnswerWebSource] = Field(default_factory=list)
