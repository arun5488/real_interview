from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.real_interview import logger
from app.real_interview.backend.graphs.checkpointer import get_shared_checkpointer
from app.real_interview.backend.nodes.interview_nodes import (
    advance_interviewer_node,
    feedback_node,
    hr_recruiter_node,
    interviewer_opening_node,
    interviewer_turn_node,
    load_context_node,
    maybe_summarize_node,
    router_node,
    route_after_start,
    should_summarize,
)
from app.real_interview.backend.state.interview_pipeline_state import InterviewPipelineState

def _build_start_graph():
    """HR + router + first interviewer opening."""
    graph = StateGraph(InterviewPipelineState)
    graph.add_node("load_context", load_context_node)
    graph.add_node("hr_recruiter", hr_recruiter_node)
    graph.add_node("router", router_node)
    graph.add_node("interviewer_opening", interviewer_opening_node)

    graph.add_edge(START, "load_context")
    graph.add_conditional_edges(
        "load_context",
        route_after_start,
        {"continue": "hr_recruiter", "end": END},
    )
    graph.add_conditional_edges(
        "hr_recruiter",
        route_after_start,
        {"continue": "router", "end": END},
    )
    graph.add_conditional_edges(
        "router",
        route_after_start,
        {"continue": "interviewer_opening", "end": END},
    )
    graph.add_edge("interviewer_opening", END)
    return graph.compile(checkpointer=get_shared_checkpointer())


def _build_chat_graph():
    """Candidate message → interviewer → optional summarize."""
    graph = StateGraph(InterviewPipelineState)
    graph.add_node("interviewer_turn", interviewer_turn_node)
    graph.add_node("summarize", maybe_summarize_node)

    graph.add_edge(START, "interviewer_turn")
    graph.add_conditional_edges(
        "interviewer_turn",
        should_summarize,
        {"summarize": "summarize", "skip_summarize": END},
    )
    graph.add_edge("summarize", END)
    return graph.compile(checkpointer=get_shared_checkpointer())


def _build_feedback_graph():
    graph = StateGraph(InterviewPipelineState)
    graph.add_node("summarize", maybe_summarize_node)
    graph.add_node("feedback", feedback_node)
    graph.add_edge(START, "summarize")
    graph.add_edge("summarize", "feedback")
    graph.add_edge("feedback", END)
    return graph.compile(checkpointer=get_shared_checkpointer())


def _build_advance_graph():
    graph = StateGraph(InterviewPipelineState)
    graph.add_node("advance", advance_interviewer_node)
    graph.add_node("interviewer_opening", interviewer_opening_node)
    graph.add_edge(START, "advance")
    graph.add_conditional_edges(
        "advance",
        lambda s: "opening" if not s.get("interview_complete") else "done",
        {"opening": "interviewer_opening", "done": END},
    )
    graph.add_edge("interviewer_opening", END)
    return graph.compile(checkpointer=get_shared_checkpointer())


@lru_cache(maxsize=1)
def get_start_graph():
    logger.info("[interview_graph] compile start graph")
    return _build_start_graph()


@lru_cache(maxsize=1)
def get_chat_graph():
    logger.info("[interview_graph] compile chat graph")
    return _build_chat_graph()


@lru_cache(maxsize=1)
def get_feedback_graph():
    logger.info("[interview_graph] compile feedback graph")
    return _build_feedback_graph()


@lru_cache(maxsize=1)
def get_advance_graph():
    logger.info("[interview_graph] compile advance graph")
    return _build_advance_graph()


def make_thread_id(customer_id: str, resume_id: str, job_application_id: str) -> str:
    return f"{customer_id}:{resume_id}:{job_application_id}"
