"""Extract interviewer question / candidate answer pairs from stored chat messages."""

import re
from typing import Any, Dict, List

from app.real_interview.backend.services.question_bank import extract_question_from_message

_SKIP_PHRASES = (
    "do you have any questions",
    "before we wrap up",
    "thank you for your time",
    "that concludes our interview",
    "we'll share feedback with you",
)

_INTERVIEWER_PREFIX = re.compile(r"^\[(I\d+)\]:\s*", re.IGNORECASE)


def _is_skippable_assistant(content: str) -> bool:
    lower = (content or "").strip().lower()
    if not lower:
        return True
    return any(phrase in lower for phrase in _SKIP_PHRASES)


def _interviewer_label(content: str) -> str:
    match = _INTERVIEWER_PREFIX.match((content or "").strip())
    return match.group(1).upper() if match else ""


def _is_technical_interviewer_message(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    if not _INTERVIEWER_PREFIX.match(text):
        return False
    if _is_skippable_assistant(text):
        return False
    question = extract_question_from_message(text)
    if not question:
        return False
    if "?" not in question and len(question) < 25:
        return False
    return True


def extract_interview_qa_pairs(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Pair each technical interviewer question with the candidate's next reply.

    When multiple interviewers ask before one candidate answer, each question
    receives the same candidate_answer.
    """
    pairs: List[Dict[str, str]] = []
    pending: List[Dict[str, str]] = []

    for message in messages or []:
        role = (message.get("role") or "").strip().lower()
        content = (message.get("content") or "").strip()
        if not content:
            continue

        if role == "assistant":
            if _is_technical_interviewer_message(content):
                pending.append(
                    {
                        "interviewer": _interviewer_label(content),
                        "question": extract_question_from_message(content),
                        "full_question": content,
                    }
                )
            elif _is_skippable_assistant(content):
                pending = []
            continue

        if role == "user" and pending:
            for item in pending:
                pairs.append(
                    {
                        "interviewer": item["interviewer"],
                        "question": item["question"],
                        "candidate_answer": content,
                    }
                )
            pending = []

    return pairs
