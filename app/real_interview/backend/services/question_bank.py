import hashlib
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo.collection import Collection
from pymongo.errors import CollectionInvalid, PyMongoError

from app.real_interview import logger
from app.real_interview.backend.config.configuration import get_question_bank_config
from app.real_interview.backend.utils.mongodb import connect_mongodb

_VALID_LEVELS = frozenset({"junior", "mid", "senior"})


def normalize_job_role(role: str) -> str:
    return re.sub(r"\s+", " ", (role or "").strip().lower())


def normalize_experience_level(level: str) -> str:
    value = (level or "").strip().lower()
    if value in _VALID_LEVELS:
        return value
    if "junior" in value or value == "entry":
        return "junior"
    if "senior" in value or "lead" in value:
        return "senior"
    if "mid" in value:
        return "mid"
    return "junior"


def hash_question_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def extract_question_from_message(content: str) -> str:
    """Best-effort extraction of the question portion of an interviewer message."""
    text = (content or "").strip()
    text = re.sub(r"^\[[^\]]+\]:\s*", "", text, count=1)
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        if "?" in sentence:
            return sentence.strip()
    if len(text) > 280:
        return text[:280].strip() + "..."
    return text


def _collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_QUESTION_BANK", "interview_question_bank").strip()


def _get_collection() -> tuple[Any, Collection]:
    client = connect_mongodb()
    db = client[os.getenv("MONGODB_DB_NAME", "real_interview").strip()]
    coll_name = _collection_name()
    names = set(db.list_collection_names())
    if coll_name not in names:
        try:
            db.create_collection(coll_name)
            logger.info("[question_bank] created collection %r", coll_name)
        except CollectionInvalid:
            pass
    collection = db[coll_name]
    collection.create_index(
        [("job_role_key", 1), ("experience_level", 1)],
        unique=True,
        name="unique_role_level",
    )
    return client, collection


def load_question_seeds(job_role: str, experience_level: str) -> List[Dict[str, Any]]:
    """Return question seeds for role/level. Empty list if none or on error (never raises)."""
    role_key = normalize_job_role(job_role)
    level = normalize_experience_level(experience_level)
    if not role_key:
        return []

    client = None
    try:
        client, collection = _get_collection()
        doc = collection.find_one({"job_role_key": role_key, "experience_level": level})
        if not doc:
            logger.info("[question_bank] no bank for role=%s level=%s", role_key, level)
            return []
        questions = doc.get("questions") or []
        cfg = get_question_bank_config()
        max_return = int(cfg.get("max_questions_per_bucket", 200))
        return [dict(q) for q in questions[:max_return] if isinstance(q, dict) and q.get("text")]
    except Exception:
        logger.exception("[question_bank] load_question_seeds failed role=%s", role_key)
        return []
    finally:
        if client is not None:
            client.close()


def filter_seeds_for_interviewer(
    seeds: List[Dict[str, Any]],
    asked_hashes: set[str],
    interviewer_type: str,
    *,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    cfg = get_question_bank_config()
    max_out = limit or int(cfg.get("seeds_per_interviewer", 12))
    out: List[Dict[str, Any]] = []
    for item in seeds:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        style = (item.get("interviewer_style") or "").strip().lower()
        if style and style != interviewer_type:
            continue
        if hash_question_text(text) in asked_hashes:
            continue
        out.append(item)
        if len(out) >= max_out:
            break
    return out


def append_questions_to_bank(
    job_role: str,
    experience_level: str,
    questions: List[Dict[str, Any]],
    *,
    source: str = "interview",
) -> int:
    """
    Append deduplicated questions to the bank. Returns count added. Never raises.
    """
    role_key = normalize_job_role(job_role)
    level = normalize_experience_level(experience_level)
    if not role_key or not questions:
        return 0

    cfg = get_question_bank_config()
    max_per_bucket = int(cfg.get("max_questions_per_bucket", 200))

    client = None
    try:
        client, collection = _get_collection()
        doc = collection.find_one({"job_role_key": role_key, "experience_level": level}) or {}
        existing = list(doc.get("questions") or [])
        known_hashes = {hash_question_text((q.get("text") or "")) for q in existing if isinstance(q, dict)}

        added = 0
        now = datetime.now(timezone.utc)
        for raw in questions:
            if not isinstance(raw, dict):
                continue
            text = (raw.get("text") or "").strip()
            if len(text) < 12:
                continue
            qh = hash_question_text(text)
            if qh in known_hashes:
                continue
            entry = {
                "id": qh,
                "text": text,
                "topic": (raw.get("topic") or "").strip(),
                "interviewer_style": (raw.get("interviewer_style") or "").strip().lower(),
                "source": source,
                "created_at": now,
            }
            existing.append(entry)
            known_hashes.add(qh)
            added += 1

        if added == 0:
            return 0

        if len(existing) > max_per_bucket:
            existing = existing[-max_per_bucket:]

        collection.update_one(
            {"job_role_key": role_key, "experience_level": level},
            {
                "$set": {
                    "job_role_key": role_key,
                    "job_role_display": (job_role or "").strip(),
                    "experience_level": level,
                    "questions": existing,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        logger.info(
            "[question_bank] appended %s question(s) role=%s level=%s total=%s",
            added,
            role_key,
            level,
            len(existing),
        )
        return added
    except PyMongoError:
        logger.exception("[question_bank] append failed role=%s", role_key)
        return 0
    except Exception:
        logger.exception("[question_bank] append unexpected error role=%s", role_key)
        return 0
    finally:
        if client is not None:
            client.close()
