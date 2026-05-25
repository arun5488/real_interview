import os
from typing import Optional

from langchain_core.tools import tool

from app.real_interview import logger


def _tavily_client():
    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise RuntimeError(
            "tavily-python is not installed. Add it to requirements.txt and pip install."
        ) from exc

    api_key = os.getenv("TAVILY_API_KEY", "").strip().strip("'\"")
    if not api_key:
        raise ValueError("TAVILY_API_KEY is not set in the environment or .env file")
    return TavilyClient(api_key=api_key)


@tool
def tavily_web_search(query: str) -> str:
    """
    Search the web for technical interview topics, frameworks, or role-related facts.
    Use when you need up-to-date or factual context beyond the resume and job description.
    """
    logger.info("[tavily_web_search] query=%s", (query or "")[:120])
    if not query or not query.strip():
        return "No search query provided."

    max_results = int(os.getenv("TAVILY_MAX_RESULTS", "5").strip() or "5")
    try:
        client = _tavily_client()
        response = client.search(query=query.strip(), max_results=max_results)
        results = response.get("results") if isinstance(response, dict) else []
        if not results:
            return "No search results found."

        parts = []
        for i, item in enumerate(results[:max_results], start=1):
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            content = (item.get("content") or "").strip()
            url = (item.get("url") or "").strip()
            block = f"{i}. {title}\n{content}"
            if url:
                block += f"\nSource: {url}"
            parts.append(block)
        return "\n\n".join(parts) if parts else "No search results found."
    except Exception as exc:
        logger.exception("[tavily_web_search] failed")
        return f"Search unavailable: {exc}"


def get_interviewer_tools() -> list:
    """Tools bound to technical interviewer agents."""
    return [tavily_web_search]
