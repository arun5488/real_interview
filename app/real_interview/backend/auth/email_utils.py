import re
from typing import Any, Dict, Optional

from pymongo.collection import Collection

from app.real_interview import logger


def normalize_email(email: str) -> str:
    """Normalize email for storage and lookup (trim + lowercase)."""
    if not isinstance(email, str):
        return ""
    return email.strip().lower()


def find_user_by_email(collection: Collection, email: str) -> Optional[Dict[str, Any]]:
    """
    Find user by email, normalizing case. Migrates legacy mixed-case emails to lowercase.
    """
    raw = (email or "").strip()
    if not raw:
        return None

    normalized = normalize_email(raw)
    doc = collection.find_one({"email": normalized})
    if doc:
        return doc

    doc = collection.find_one({"email": {"$regex": f"^{re.escape(raw)}$", "$options": "i"}})
    if not doc:
        return None

    stored = doc.get("email") or ""
    if stored != normalized:
        logger.info("[email_utils] migrating email to lowercase user_id=%s", doc.get("_id"))
        collection.update_one({"_id": doc["_id"]}, {"$set": {"email": normalized}})
        doc["email"] = normalized
    return doc
