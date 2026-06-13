import html
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import CollectionInvalid, PyMongoError

from app.real_interview import logger
from app.real_interview.backend.agents.job_application_agent import JobApplicationAgent
from app.real_interview.backend.utils.mongodb import get_mongodb_database

APPLICATION_LINK_NA = "NA"
INPUT_MODE_LINK = "link"
INPUT_MODE_DESCRIPTION = "description"
ERROR_CODE_JOB_URL_BLOCKED = "job_url_blocked"

JOB_URL_BLOCKED_MESSAGE = (
    "This job board blocked automated access to that link. "
    "Switch to Job description, paste the full job posting text, and submit again."
)

_BLOCKED_HTTP_STATUS = frozenset({401, 403, 429, 451, 503})
_BLOCKED_PAGE_MARKERS = (
    "access denied",
    "please enable cookies",
    "just a moment",
    "cloudflare",
    "captcha",
    "verify you are human",
    "bot detection",
    "unusual traffic",
    "request blocked",
)


def _success(status_code: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status_code": status_code}
    if payload:
        result.update(payload)
    return result


def _error(status_code: int, message: str, **extra: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status_code": status_code, "error": message}
    result.update(extra)
    return result


def _page_text_looks_blocked(text: str) -> bool:
    if not text or not text.strip():
        return True
    stripped = text.strip()
    if len(stripped) < 120:
        lower = stripped.lower()
        return any(marker in lower for marker in _BLOCKED_PAGE_MARKERS)
    lower = stripped.lower()
    hits = sum(1 for marker in _BLOCKED_PAGE_MARKERS if marker in lower)
    return hits >= 2


def _url_fetch_error_response(exc: Exception) -> Dict[str, Any]:
    """Map URL fetch failures to user-facing errors; flag job-board blocks explicitly."""
    if isinstance(exc, HTTPError) and exc.code in _BLOCKED_HTTP_STATUS:
        logger.warning("[job_application] job board blocked fetch (HTTP %s)", exc.code)
        return _error(
            422,
            JOB_URL_BLOCKED_MESSAGE,
            error_code=ERROR_CODE_JOB_URL_BLOCKED,
            suggest_input_mode=INPUT_MODE_DESCRIPTION,
        )

    if isinstance(exc, ValueError) and "could not extract readable text" in str(exc).lower():
        logger.warning("[job_application] job board returned no readable posting text")
        return _error(
            422,
            JOB_URL_BLOCKED_MESSAGE,
            error_code=ERROR_CODE_JOB_URL_BLOCKED,
            suggest_input_mode=INPUT_MODE_DESCRIPTION,
        )

    if isinstance(exc, (HTTPError, URLError, TimeoutError)):
        logger.warning("[job_application] URL fetch failed: %s", exc)
        return _error(
            422,
            (
                "Could not read the job posting from that link. "
                "The site may block automated access — switch to Job description, "
                "paste the full posting text, and submit again."
            ),
            suggest_input_mode=INPUT_MODE_DESCRIPTION,
        )

    logger.warning("[job_application] unexpected URL fetch error: %s", exc)
    return _error(
        422,
        (
            "Could not read the job posting from that link. "
            "Switch to Job description, paste the full posting text, and submit again."
        ),
        suggest_input_mode=INPUT_MODE_DESCRIPTION,
    )


def _get_db_name() -> str:
    name = os.getenv("MONGODB_DB_NAME", "").strip()
    if not name:
        raise ValueError("MONGODB_DB_NAME is not set in the environment or .env file")
    return name


def _get_users_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_USERS", "authentications").strip()


def _get_job_application_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_JOB_APPLICATIONS", "job_application").strip()


def _as_customer_object_id(customer_id: str) -> ObjectId:
    if not isinstance(customer_id, str) or not customer_id.strip():
        raise ValueError("customer_id must be a non-empty string")
    try:
        return ObjectId(customer_id.strip())
    except InvalidId as exc:
        raise ValueError("customer_id is not a valid ObjectId") from exc


def _is_valid_http_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _fetch_url_as_text(url: str, *, timeout: int = 20) -> str:
    logger.info("[job_application] fetching URL: %s", url)
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RealInterview/1.0; +https://real-interview.local)",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        content_type = resp.headers.get("Content-Type", "") if resp.headers else ""
    charset = "utf-8"
    if "charset=" in (content_type or ""):
        match = re.search(r"charset=([^\s;]+)", content_type, re.I)
        if match:
            charset = match.group(1).strip("'\"")

    text = raw.decode(charset, errors="replace")
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise ValueError("could not extract readable text from the job posting URL")
    return text


def _ensure_job_application_indexes(collection) -> None:
    collection.create_index(
        [("customer_id", 1), ("job_application_ts", -1)],
        name="customer_id_job_application_ts",
    )


_job_apps_ready = False


def _get_collections() -> Tuple[Any, Any]:
    global _job_apps_ready
    db = get_mongodb_database(_get_db_name())
    users = db[_get_users_collection_name()]
    job_apps = db[_get_job_application_collection_name()]
    if not _job_apps_ready:
        names = set(db.list_collection_names())
        coll_name = _get_job_application_collection_name()
        if coll_name not in names:
            try:
                db.create_collection(coll_name)
                logger.info("[job_application] created collection %r", coll_name)
            except CollectionInvalid:
                logger.warning("[job_application] collection %r already exists (race)", coll_name)
        _ensure_job_application_indexes(job_apps)
        _job_apps_ready = True
    return users, job_apps


def _customer_exists(users_collection, customer_oid: ObjectId) -> bool:
    return users_collection.find_one({"_id": customer_oid}, {"_id": 1}) is not None


def submit_job_application(
    *,
    customer_id: str,
    input_mode: str,
    application_link: Optional[str] = None,
    job_description_text: Optional[str] = None,
    parse_agent: Optional[JobApplicationAgent] = None,
) -> Dict[str, Any]:
    """
    Persist a job application record for a customer.

    input_mode: ``link`` (fetch URL) or ``description`` (user-provided text).
    """
    logger.info("[job_application] submit_job_application start mode=%s", input_mode)
    agent = parse_agent if parse_agent is not None else JobApplicationAgent()

    try:
        try:
            customer_oid = _as_customer_object_id(customer_id)
        except ValueError as exc:
            return _error(400, str(exc))

        mode = (input_mode or "").strip().lower()
        if mode not in (INPUT_MODE_LINK, INPUT_MODE_DESCRIPTION):
            return _error(400, "input_mode must be 'link' or 'description'")

        users_coll, job_coll = _get_collections()
        if not _customer_exists(users_coll, customer_oid):
            return _error(404, "customer not found")

        stored_link = APPLICATION_LINK_NA
        source_text = ""

        if mode == INPUT_MODE_LINK:
            link = (application_link or "").strip()
            if not link:
                return _error(400, "application_link is required when input_mode is link")
            if not _is_valid_http_url(link):
                return _error(400, "application_link must be a valid http or https URL")
            stored_link = link
            try:
                source_text = _fetch_url_as_text(link)
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                return _url_fetch_error_response(exc)

            if _page_text_looks_blocked(source_text):
                logger.warning(
                    "[job_application] fetched page looks like a block/captcha for %s",
                    link,
                )
                return _error(
                    422,
                    JOB_URL_BLOCKED_MESSAGE,
                    error_code=ERROR_CODE_JOB_URL_BLOCKED,
                    suggest_input_mode=INPUT_MODE_DESCRIPTION,
                )

            extracted = agent.extract_from_text(
                source_text,
                source="link",
                application_link=link,
            )
        else:
            text = (job_description_text or "").strip()
            if not text:
                return _error(400, "job_description_text is required when input_mode is description")
            source_text = text
            extracted = agent.extract_from_text(text, source="description")

        job_role = extracted.get("job_role") or ""
        job_description = extracted.get("job_description") or ""
        if not job_description.strip():
            job_description = source_text.strip()[:12000]

        job_application_ts = datetime.now(timezone.utc)
        doc = {
            "customer_id": customer_oid,
            "job_role": job_role,
            "application_link": stored_link,
            "job_description": job_description,
            "job_application_ts": job_application_ts,
        }
        result = job_coll.insert_one(doc)

        payload = {
            "job_application_id": str(result.inserted_id),
            "customer_id": str(customer_oid),
            "job_role": job_role,
            "application_link": stored_link,
            "job_description": job_description,
            "job_application_ts": job_application_ts.isoformat(),
            "message": "job application saved successfully",
        }
        logger.info(
            "[job_application] saved id=%s customer_id=%s",
            result.inserted_id,
            customer_oid,
        )
        return _success(201, payload)

    except PyMongoError:
        logger.exception("[job_application] MongoDB error")
        raise
    except Exception:
        logger.exception("[job_application] unexpected error")
        raise


def get_job_application_for_customer(
    customer_id: str,
    job_application_id: str,
) -> Dict[str, Any]:
    """Load one job application document owned by the customer."""
    logger.info("[job_application] get_job_application_for_customer start")
    customer_oid = _as_customer_object_id(customer_id)
    app_oid = _as_customer_object_id(job_application_id)
    users_coll, job_coll = _get_collections()
    if not _customer_exists(users_coll, customer_oid):
        raise ValueError("customer not found")

    doc = job_coll.find_one({"_id": app_oid, "customer_id": customer_oid})
    if not doc:
        raise ValueError("job application not found for this user")

    ts = doc.get("job_application_ts")
    return {
        "job_application_id": str(doc["_id"]),
        "customer_id": str(customer_oid),
        "job_role": (doc.get("job_role") or "").strip(),
        "application_link": (doc.get("application_link") or "").strip(),
        "job_description": (doc.get("job_description") or "").strip(),
        "job_application_ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
    }
