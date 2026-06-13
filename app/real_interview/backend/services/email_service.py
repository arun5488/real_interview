import json
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any, Dict, Optional, Tuple

from app.real_interview import logger


def email_provider() -> str:
    """smtp (local/dev) or resend (HTTPS — works on Render free tier)."""
    return os.getenv("EMAIL_PROVIDER", "smtp").strip().lower()


def _smtp_settings() -> Tuple[str, int, str, str, bool, str, str] | None:
    host = os.getenv("SMTP_HOST", "").strip()
    port_raw = os.getenv("SMTP_PORT", "587").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not (host and user and password):
        return None
    try:
        port = int(port_raw)
    except ValueError:
        logger.error("[email_service] invalid SMTP_PORT=%s", port_raw)
        return None
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() not in ("0", "false", "no")
    from_email = os.getenv("FEEDBACK_FROM_EMAIL", "").strip() or user
    from_name = os.getenv("FEEDBACK_FROM_NAME", "Real Interview").strip()
    return host, port, user, password, use_tls, from_email, from_name


def _resend_settings() -> Tuple[str, str, str] | None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM_EMAIL", "").strip() or os.getenv("FEEDBACK_FROM_EMAIL", "").strip()
    from_name = os.getenv("FEEDBACK_FROM_NAME", "Real Interview").strip()
    if not api_key or not from_email:
        return None
    return api_key, from_email, from_name


def is_smtp_available() -> bool:
    if email_provider() == "resend":
        return _resend_settings() is not None
    return _smtp_settings() is not None


def interview_feedback_email_enabled() -> bool:
    """Master switch for emailing post-interview feedback to candidates."""
    raw = os.getenv("SEND_INTERVIEW_FEEDBACK_EMAIL", "true").strip().lower()
    return raw not in ("0", "false", "no")


def feedback_recipient() -> str:
    """Mailbox that receives website feedback submissions."""
    explicit = os.getenv("FEEDBACK_TO_EMAIL", "").strip()
    if explicit:
        return explicit
    admin_raw = os.getenv("ADMIN_EMAILS", "").strip()
    if admin_raw:
        return admin_raw.split(",")[0].strip()
    return ""


def is_smtp_configured() -> bool:
    return is_smtp_available() and bool(feedback_recipient())


def _send_via_smtp(
    *,
    to_email: str,
    subject: str,
    body: str,
    reply_to: str = "",
) -> tuple[bool, str]:
    settings = _smtp_settings()
    if not settings:
        logger.error("[email_service] SMTP not configured")
        return False, "email delivery is not configured"

    host, port, user, password, use_tls, from_email, from_name = settings
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True, ""
    except smtplib.SMTPException:
        logger.exception("[email_service] SMTP error")
        return False, "failed to send email"
    except OSError:
        logger.exception("[email_service] network error connecting to SMTP")
        return False, (
            "failed to connect to mail server (Render free tier blocks SMTP ports 587/465 — "
            "set EMAIL_PROVIDER=resend or upgrade Render)"
        )


def _send_via_resend(
    *,
    to_email: str,
    subject: str,
    body: str,
    reply_to: str = "",
) -> tuple[bool, str]:
    settings = _resend_settings()
    if not settings:
        logger.error("[email_service] Resend not configured")
        return False, "email delivery is not configured"

    api_key, from_email, from_name = settings
    payload: Dict[str, Any] = {
        "from": f"{from_name} <{from_email}>",
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if 200 <= response.status < 300:
                return True, ""
        return False, "failed to send email"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        logger.error("[email_service] Resend HTTP %s: %s", exc.code, detail)
        return False, "failed to send email"
    except urllib.error.URLError:
        logger.exception("[email_service] Resend network error")
        return False, "failed to connect to mail server"


def _send_email(*, to_email: str, subject: str, body: str, reply_to: str = "") -> tuple[bool, str]:
    if email_provider() == "resend":
        return _send_via_resend(to_email=to_email, subject=subject, body=body, reply_to=reply_to)
    return _send_via_smtp(to_email=to_email, subject=subject, body=body, reply_to=reply_to)


def _format_interview_feedback_body(
    *,
    feedback: Dict[str, Any],
    role_applied_for: str = "",
    session_id: str = "",
) -> str:
    lines = ["Your Real Interview feedback", ""]
    if role_applied_for:
        lines.append(f"Role: {role_applied_for}")
    if session_id:
        lines.append(f"Session: {session_id}")
    lines.append("")

    assessment = (feedback.get("overall_assessment") or "").strip()
    if assessment:
        lines.extend(["Overall assessment", assessment, ""])

    strengths = feedback.get("strengths") or []
    if strengths:
        lines.append("Strengths")
        for item in strengths:
            text = (item or "").strip()
            if text:
                lines.append(f"  • {text}")
        lines.append("")

    improvements = feedback.get("areas_to_improve") or []
    if improvements:
        lines.append("Areas to improve")
        for item in improvements:
            text = (item or "").strip()
            if text:
                lines.append(f"  • {text}")
        lines.append("")

    recommendation = (feedback.get("recommendation") or "").strip()
    if recommendation:
        lines.extend(["Recommendation", recommendation, ""])

    decision = (feedback.get("interview_decision") or "").strip()
    if decision:
        lines.extend(["Interview decision", decision, ""])

    detailed = (feedback.get("detailed_feedback") or "").strip()
    if detailed:
        lines.extend(["Detailed feedback", detailed, ""])

    lines.extend(
        [
            "—",
            "This message was sent from Real Interview. Keep practicing and good luck!",
        ]
    )
    return "\n".join(lines)


def send_interview_feedback_email(
    *,
    candidate_email: str,
    feedback: Dict[str, Any],
    role_applied_for: str = "",
    session_id: str = "",
) -> tuple[bool, str]:
    """Email post-interview feedback to the candidate."""
    if not interview_feedback_email_enabled():
        return False, "interview feedback email is disabled"
    if not is_smtp_available():
        return False, "email delivery is not configured"

    to_email = (candidate_email or "").strip().lower()
    if not to_email:
        return False, "candidate email is missing"

    role = (role_applied_for or "").strip()
    subject = "[Real Interview] Your interview feedback"
    if role:
        subject = f"[Real Interview] Feedback for {role}"

    body = _format_interview_feedback_body(
        feedback=feedback,
        role_applied_for=role,
        session_id=session_id,
    )
    ok, err = _send_email(to_email=to_email, subject=subject, body=body)
    if ok:
        logger.info("[email_service] interview feedback email sent session_id=%s", session_id)
    return ok, err


def send_feedback_email(
    *,
    message: str,
    contact_email: str = "",
    category: str = "general",
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    client_ip: str = "",
) -> tuple[bool, str]:
    """
    Send website feedback to the configured admin mailbox.
    Returns (success, error_message).
    """
    if not is_smtp_configured():
        logger.error("[email_service] email not configured")
        return False, "email delivery is not configured"

    to_email = feedback_recipient()
    subject = f"[Real Interview] Website feedback ({category})"
    if contact_email:
        subject = f"[Real Interview] Feedback from {contact_email} ({category})"

    lines = [
        "New website feedback",
        "",
        f"Category: {category}",
        f"Contact email: {contact_email or '(not provided)'}",
    ]
    if user_id or user_email:
        lines.append(f"Signed-in user: {user_email or '(unknown)'} (id: {user_id or '—'})")
    if client_ip:
        lines.append(f"IP: {client_ip}")
    lines.extend(["", "Message:", message.strip(), ""])

    ok, err = _send_email(
        to_email=to_email,
        subject=subject,
        body="\n".join(lines),
        reply_to=contact_email.strip() if contact_email else "",
    )
    if ok:
        logger.info("[email_service] feedback email sent category=%s", category)
    return ok, err
