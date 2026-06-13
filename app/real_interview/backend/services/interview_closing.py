"""Interview closing phase: limits, detection, and panel messages."""

import re

from app.real_interview.backend.config.configuration import get_interview_limits_config


def max_questions_per_interviewer() -> int:
    return int(get_interview_limits_config().get("max_questions_per_interviewer", 8))


def max_candidate_qa_turns() -> int:
    return int(get_interview_limits_config().get("max_candidate_qa_turns", 2))


def _normalize_counts(raw: dict | list | None, panel_size: int) -> dict[int, int]:
    counts: dict[int, int] = {i: 0 for i in range(panel_size)}
    if isinstance(raw, dict):
        for key, value in raw.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < panel_size:
                counts[idx] = int(value or 0)
    elif isinstance(raw, list):
        for idx, value in enumerate(raw):
            if idx < panel_size:
                counts[idx] = int(value or 0)
    return counts


def all_panelists_at_question_limit(
    counts: dict[int, int] | dict | list | None,
    panel_size: int,
) -> bool:
    if panel_size <= 0:
        return False
    normalized = _normalize_counts(counts, panel_size)
    limit = max_questions_per_interviewer()
    return all(normalized.get(i, 0) >= limit for i in range(panel_size))


def increment_interviewer_question_count(
    counts: dict[int, int] | dict | list | None,
    panel_size: int,
    interviewer_index: int,
    *,
    delta: int = 1,
) -> dict[int, int]:
    normalized = _normalize_counts(counts, panel_size)
    if 0 <= interviewer_index < panel_size:
        normalized[interviewer_index] = normalized.get(interviewer_index, 0) + delta
    return normalized


def counts_for_state(counts: dict[int, int]) -> dict[str, int]:
    return {str(k): v for k, v in counts.items()}


def counts_from_state(raw: dict | list | None, panel_size: int) -> dict[int, int]:
    return _normalize_counts(raw, panel_size)


_NO_QUESTION_PATTERNS = (
    r"^\s*no\s*[.!]?\s*$",
    r"\bno questions?\b",
    r"\bnothing to ask\b",
    r"\bdon'?t have any questions?\b",
    r"\bdo not have any questions?\b",
    r"\bthat'?s all\b",
    r"\bi'?m good\b",
    r"\ball good\b",
    r"\bno,?\s*thank(s| you)\b",
)


def candidate_declined_questions(text: str) -> bool:
    """True when the candidate indicates they have no questions for the panel."""
    raw = (text or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    if "?" in raw and len(raw) > 15:
        if not re.search(r"^\s*no\s*\?", lowered):
            return False
    for pattern in _NO_QUESTION_PATTERNS:
        if re.search(pattern, lowered):
            return True
    return False


def candidate_asked_question(text: str) -> bool:
    raw = (text or "").strip()
    if not raw or candidate_declined_questions(raw):
        return False
    if "?" in raw:
        return True
    lowered = raw.lower()
    starters = ("what ", "how ", "why ", "when ", "where ", "who ", "can ", "could ", "is ", "are ", "do ", "does ")
    return any(lowered.startswith(s) for s in starters)


def ask_candidate_questions_message(interviewer_index: int) -> str:
    code = f"I{interviewer_index + 1}"
    return (
        f"[{code}]: We've covered a solid set of topics. Before we wrap up, "
        f"do you have any questions for us about the role, the team, or the interview process?"
    )


def panel_closing_message(interviewer_index: int = 0) -> str:
    code = f"I{interviewer_index + 1}"
    return (
        f"[{code}]: Thank you for your time today. That concludes our interview. "
        f"We'll share feedback with you shortly."
    )
