import os
import threading
from typing import Optional

from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

from app.real_interview import logger
from app.real_interview.backend.utils.mongodb import connect_mongodb, get_mongodb_uri

_lock = threading.Lock()
_client: Optional[MongoClient] = None
_checkpointer: Optional[MongoDBSaver] = None


def _db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _checkpoint_collection() -> str:
    return os.getenv("MONGODB_CHECKPOINT_COLLECTION", "checkpoints").strip()


def _checkpoint_writes_collection() -> str:
    return os.getenv("MONGODB_CHECKPOINT_WRITES_COLLECTION", "checkpoint_writes").strip()


def get_shared_checkpointer() -> MongoDBSaver:
    """
    Process-wide MongoDB checkpointer shared by all interview graphs.

    Checkpoints are stored in MongoDB so state survives restarts and is visible
    across Gunicorn workers.
    """
    global _client, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    with _lock:
        if _checkpointer is not None:
            return _checkpointer

        uri = get_mongodb_uri()
        _client = connect_mongodb(uri)
        _checkpointer = MongoDBSaver(
            _client,
            db_name=_db_name(),
            checkpoint_collection_name=_checkpoint_collection(),
            writes_collection_name=_checkpoint_writes_collection(),
        )
        logger.info(
            "[checkpointer] MongoDBSaver ready db=%s checkpoints=%s writes=%s",
            _db_name(),
            _checkpoint_collection(),
            _checkpoint_writes_collection(),
        )
        return _checkpointer


def delete_thread_checkpoints(thread_id: str) -> None:
    """Remove LangGraph checkpoint data for an interview thread."""
    if not thread_id or not str(thread_id).strip():
        return
    thread_id = str(thread_id).strip()
    try:
        get_shared_checkpointer().delete_thread(thread_id)
        logger.info("[checkpointer] deleted thread checkpoints thread_id=%s", thread_id)
    except Exception:
        logger.exception("[checkpointer] failed to delete thread_id=%s", thread_id)
