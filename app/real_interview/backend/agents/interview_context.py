import json
from typing import Any, Dict


def format_parsed_resume(parsed_data: Dict[str, Any]) -> str:
    if not parsed_data:
        return "(no resume data)"
    return json.dumps(parsed_data, indent=2, default=str)[:12000]


def format_first_impression(first_impression: Dict[str, Any]) -> str:
    if not first_impression:
        return "(no candidate summary yet)"
    return json.dumps(first_impression, indent=2, default=str)


def format_messages_for_summary(messages: list) -> str:
    lines = []
    for msg in messages:
        role = getattr(msg, "type", None) or msg.__class__.__name__
        content = getattr(msg, "content", str(msg))
        if isinstance(content, list):
            content = str(content)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)[:20000]
