import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

from app.real_interview import logger

_DEFAULT_INTERVIEW: Dict[str, Any] = {
    "summarizer": {
        "token_threshold": 1500,
        "max_summary_chars": 8000,
        "input_max_chars": 16000,
    },
    "feedback": {"use_summary_primary": True},
    "question_bank": {
        "seeds_per_interviewer": 12,
        "max_questions_per_bucket": 200,
        "extract_max_chars": 12000,
    },
}


def _params_file_path() -> Path:
    env_path = os.getenv("PARAMS_PATH", "").strip()
    if env_path:
        return Path(env_path)
    # Project root: .../real_interview/params.yaml
    return Path(__file__).resolve().parents[4] / "params.yaml"


@lru_cache(maxsize=1)
def load_params() -> Dict[str, Any]:
    path = _params_file_path()
    logger.info("[configuration] loading params from %s", path)
    if not path.is_file():
        logger.warning("[configuration] params file not found at %s; using defaults", path)
        return {"interview": _DEFAULT_INTERVIEW}
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            logger.warning("[configuration] params root is not a mapping; using defaults")
            return {"interview": _DEFAULT_INTERVIEW}
        logger.info("[configuration] params loaded successfully")
        return data
    except Exception:
        logger.exception("[configuration] failed to load params from %s", path)
        return {"interview": _DEFAULT_INTERVIEW}


def get_interview_config() -> Dict[str, Any]:
    params = load_params()
    interview = params.get("interview")
    if not isinstance(interview, dict):
        logger.warning("[configuration] interview section missing; using defaults")
        return dict(_DEFAULT_INTERVIEW)
    merged = dict(_DEFAULT_INTERVIEW)
    for key, value in interview.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def get_summarizer_config() -> Dict[str, Any]:
    return get_interview_config().get("summarizer", _DEFAULT_INTERVIEW["summarizer"])


def get_feedback_config() -> Dict[str, Any]:
    return get_interview_config().get("feedback", _DEFAULT_INTERVIEW["feedback"])


def get_question_bank_config() -> Dict[str, Any]:
    return get_interview_config().get("question_bank", _DEFAULT_INTERVIEW["question_bank"])
