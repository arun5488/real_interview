import re
from typing import Any, Dict, List

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.real_interview import logger


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2022", "-")
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _format_iso(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _decision_label(decision: str) -> str:
    mapping = {
        "selected": "Selected",
        "not_selected": "Not selected",
        "hold": "Hold",
    }
    return mapping.get((decision or "").strip().lower(), decision or "")


def build_report_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    """Structured interview report for UI and PDF export."""
    feedback = record.get("interview_feedback") or {}
    if not isinstance(feedback, dict):
        feedback = {}

    ideal = record.get("ideal_answers_report") or {}
    if not isinstance(ideal, dict):
        ideal = {}

    return {
        "session_id": record.get("session_id") or "",
        "role_applied_for": record.get("role_applied_for") or "",
        "interview_date": _format_iso(record.get("interview_date")),
        "interview_status": record.get("interview_status") or "",
        "interview_summary": record.get("interview_summary") or "",
        "message_count": len(record.get("messages") or []),
        "feedback": {
            "overall_assessment": feedback.get("overall_assessment") or "",
            "strengths": [str(x).strip() for x in (feedback.get("strengths") or []) if str(x).strip()],
            "areas_to_improve": [
                str(x).strip() for x in (feedback.get("areas_to_improve") or []) if str(x).strip()
            ],
            "recommendation": feedback.get("recommendation") or "",
            "interview_decision": feedback.get("interview_decision") or "",
            "interview_decision_label": _decision_label(feedback.get("interview_decision") or ""),
            "detailed_feedback": feedback.get("detailed_feedback") or "",
        },
        "ideal_answers_report": {
            "avatar_summary": ideal.get("avatar_summary") or "",
            "items": ideal.get("items") or [],
        }
        if ideal
        else None,
    }


def build_report_text(payload: Dict[str, Any]) -> str:
    """Plain-text report body."""
    lines: List[str] = ["Real Interview - Session Report", ""]

    role = payload.get("role_applied_for") or ""
    if role:
        lines.append(f"Role: {role}")
    session_id = payload.get("session_id") or ""
    if session_id:
        lines.append(f"Session: {session_id}")
    interview_date = payload.get("interview_date") or ""
    if interview_date:
        lines.append(f"Date: {interview_date}")
    lines.append(f"Messages exchanged: {payload.get('message_count', 0)}")
    lines.append("")

    summary = (payload.get("interview_summary") or "").strip()
    if summary:
        lines.extend(["Interview summary", summary, ""])

    feedback = payload.get("feedback") or {}
    assessment = (feedback.get("overall_assessment") or "").strip()
    if assessment:
        lines.extend(["Overall assessment", assessment, ""])

    strengths = feedback.get("strengths") or []
    if strengths:
        lines.append("Strengths")
        for item in strengths:
            lines.append(f"  - {item}")
        lines.append("")

    improvements = feedback.get("areas_to_improve") or []
    if improvements:
        lines.append("Areas to improve")
        for item in improvements:
            lines.append(f"  - {item}")
        lines.append("")

    recommendation = (feedback.get("recommendation") or "").strip()
    if recommendation:
        lines.extend(["Recommendation", recommendation, ""])

    decision = (feedback.get("interview_decision_label") or feedback.get("interview_decision") or "").strip()
    if decision:
        lines.extend(["Interview decision", decision, ""])

    detailed = (feedback.get("detailed_feedback") or "").strip()
    if detailed:
        lines.extend(["Detailed feedback", detailed, ""])

    ideal = payload.get("ideal_answers_report") or {}
    if isinstance(ideal, dict) and (ideal.get("items") or ideal.get("avatar_summary")):
        summary = (ideal.get("avatar_summary") or "").strip()
        if summary:
            lines.extend(["Ideal candidate persona", summary, ""])
        for idx, item in enumerate(ideal.get("items") or [], start=1):
            if not isinstance(item, dict):
                continue
            question = (item.get("question") or "").strip()
            ideal_answer = (item.get("ideal_answer") or "").strip()
            if not question and not ideal_answer:
                continue
            interviewer = (item.get("interviewer") or "").strip()
            header = f"Q{idx}"
            if interviewer:
                header += f" [{interviewer}]"
            lines.append(header)
            if question:
                lines.append(f"Question: {question}")
            given = (item.get("candidate_answer") or "").strip()
            if given:
                lines.append(f"Your answer: {given}")
            if ideal_answer:
                lines.append(f"Ideal answer: {ideal_answer}")
            sources = item.get("web_sources") or []
            for source in sources:
                if not isinstance(source, dict):
                    continue
                title = (source.get("title") or "").strip()
                url = (source.get("url") or "").strip()
                if url:
                    lines.append(f"  Source: {title or url} — {url}")
            lines.append("")

    lines.extend(["-", "Generated by Real Interview"])
    return "\n".join(lines)


def _slug_filename(value: str, fallback: str = "interview-report") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip()).strip("-").lower()
    if not slug:
        slug = fallback
    return f"{slug[:60]}.pdf"


def report_download_filename(payload: Dict[str, Any]) -> str:
    role = payload.get("role_applied_for") or "interview-report"
    return _slug_filename(role)


class _ReportPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Real Interview - page {self.page_no()}", align="C")


def build_report_pdf(payload: Dict[str, Any]) -> bytes:
    """Render report payload as a PDF document."""
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(
        0,
        8,
        _clean_text("Real Interview - Session Report"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(2)

    meta_lines = []
    if payload.get("role_applied_for"):
        meta_lines.append(f"Role: {payload['role_applied_for']}")
    if payload.get("session_id"):
        meta_lines.append(f"Session: {payload['session_id']}")
    if payload.get("interview_date"):
        meta_lines.append(f"Date: {payload['interview_date']}")
    meta_lines.append(f"Messages exchanged: {payload.get('message_count', 0)}")

    pdf.set_font("Helvetica", "", 10)
    for line in meta_lines:
        pdf.multi_cell(0, 5, _clean_text(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    def section(title: str, body: str) -> None:
        text = (body or "").strip()
        if not text:
            return
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, _clean_text(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _clean_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    def bullet_section(title: str, items: List[str]) -> None:
        cleaned = [str(x).strip() for x in items if str(x).strip()]
        if not cleaned:
            return
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, _clean_text(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        for item in cleaned:
            pdf.multi_cell(0, 5, _clean_text(f"- {item}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    section("Interview summary", payload.get("interview_summary") or "")

    feedback = payload.get("feedback") or {}
    section("Overall assessment", feedback.get("overall_assessment") or "")
    bullet_section("Strengths", feedback.get("strengths") or [])
    bullet_section("Areas to improve", feedback.get("areas_to_improve") or [])
    section("Recommendation", feedback.get("recommendation") or "")
    decision = feedback.get("interview_decision_label") or feedback.get("interview_decision") or ""
    section("Interview decision", decision)
    section("Detailed feedback", feedback.get("detailed_feedback") or "")

    ideal = payload.get("ideal_answers_report") or {}
    if isinstance(ideal, dict):
        section("Ideal candidate persona", ideal.get("avatar_summary") or "")
        for idx, item in enumerate(ideal.get("items") or [], start=1):
            if not isinstance(item, dict):
                continue
            question = (item.get("question") or "").strip()
            ideal_answer = (item.get("ideal_answer") or "").strip()
            if not question and not ideal_answer:
                continue
            interviewer = (item.get("interviewer") or "").strip()
            title = f"Ideal answer {idx}"
            if interviewer:
                title += f" ({interviewer})"
            body_parts = []
            if question:
                body_parts.append(f"Question: {question}")
            given = (item.get("candidate_answer") or "").strip()
            if given:
                body_parts.append(f"Your answer: {given}")
            if ideal_answer:
                body_parts.append(f"Ideal answer: {ideal_answer}")
            sources = item.get("web_sources") or []
            source_lines = []
            for source in sources:
                if not isinstance(source, dict):
                    continue
                url = (source.get("url") or "").strip()
                if not url:
                    continue
                label = (source.get("title") or "").strip() or url
                source_lines.append(f"- {label}: {url}")
            if source_lines:
                body_parts.append("Web sources:")
                body_parts.extend(source_lines)
            section(title, "\n".join(body_parts))

    logger.info("[interview_report] pdf generated session_id=%s", payload.get("session_id"))
    return bytes(pdf.output())
