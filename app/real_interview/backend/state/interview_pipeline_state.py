from typing import Annotated, Any, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class InterviewPipelineState(TypedDict, total=False):
    """LangGraph workflow state for the interview module."""

    customer_id: str
    resume_id: str
    job_application_id: str
    session_id: str
    interview_record_id: str

    parsed_data: dict[str, Any]
    job_role: str
    job_description: str
    application_link: str

    first_impression: dict[str, Any]
    panel_plan: dict[str, Any]

    active_interviewer_index: int
    interviewer_conclusions: List[dict[str, Any]]

    question_bank_seeds: List[dict[str, Any]]
    asked_question_hashes: List[str]

    running_summary: str
    summary_snapshots: List[str]
    last_summarized_message_count: int
    force_summarize: bool

    messages: Annotated[List[BaseMessage], add_messages]

    candidate_post_interview_feedback: dict[str, Any]
    interview_complete: bool

    # active | awaiting_candidate_questions | candidate_qa
    interview_phase: str
    interviewer_question_counts: dict[str, int]
    candidate_qa_turns: int
    pending_auto_complete: bool

    error: Optional[str]
    step: str
