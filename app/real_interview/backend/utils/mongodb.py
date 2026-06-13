import os
import re
import threading
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.real_interview import logger
from dotenv import load_dotenv

load_dotenv()

_lock = threading.Lock()
_client: Optional[MongoClient] = None
_client_uri: Optional[str] = None


def _mask_mongodb_uri(uri: str) -> str:
    """
    Best-effort masking of credentials inside a MongoDB URI.

    Example:
      mongodb+srv://user:pass@host/db -> mongodb+srv://user:***@host/db
    """
    masked = re.sub(r"//([^/@:]+):([^@/]*)@", r"//\1:***@", uri)
    return masked if masked else "<hidden>"


def get_mongodb_uri() -> str:
    """Return the MongoDB connection string from MONGODB_URI (whitespace trimmed)."""
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        logger.error("`MONGODB_URI` is missing (check your `.env` file)")
        raise ValueError("MONGODB_URI is not set in the environment or .env file")
    return uri


def get_shared_mongodb_client(uri: Optional[str] = None) -> MongoClient:
    """
    Return a process-wide MongoDB client with connection pooling.

    Safe to call on every request; do not close the returned client per operation.
    """
    global _client, _client_uri
    connection_uri = (uri or get_mongodb_uri()).strip()
    if not connection_uri:
        raise ValueError("MongoDB URI is empty")

    if _client is not None and _client_uri == connection_uri:
        return _client

    with _lock:
        if _client is not None and _client_uri == connection_uri:
            return _client

        logger.info(
            "[mongodb] initializing shared client uri=%s",
            _mask_mongodb_uri(connection_uri),
        )
        client = MongoClient(
            connection_uri,
            maxPoolSize=50,
            minPoolSize=1,
            maxIdleTimeMS=45_000,
            serverSelectionTimeoutMS=10_000,
        )
        try:
            client.admin.command("ping")
        except (PyMongoError, Exception):
            client.close()
            logger.exception("[mongodb] shared client ping failed")
            raise

        _client = client
        _client_uri = connection_uri
        logger.info("[mongodb] shared client ready (pooled)")
        return _client


def connect_mongodb(uri: Optional[str] = None) -> MongoClient:
    """Backward-compatible alias for the shared pooled client."""
    return get_shared_mongodb_client(uri)


def get_mongodb_database(db_name: Optional[str] = None) -> Database:
    name = (db_name or os.getenv("MONGODB_DB_NAME", "real_interview")).strip()
    if not name:
        raise ValueError("MONGODB_DB_NAME is not set")
    return get_shared_mongodb_client()[name]


def close_shared_mongodb_client() -> None:
    """Close the shared client (tests or graceful shutdown only)."""
    global _client, _client_uri
    with _lock:
        if _client is not None:
            _client.close()
            _client = None
            _client_uri = None
            logger.info("[mongodb] shared client closed")
