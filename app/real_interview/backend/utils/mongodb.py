import os
import re
from typing import Optional

from app.real_interview import logger
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()


def _mask_mongodb_uri(uri: str) -> str:
    """
    Best-effort masking of credentials inside a MongoDB URI.

    Example:
      mongodb+srv://user:pass@host/db -> mongodb+srv://user:***@host/db
    """
    # If the URI has the usual "...://user:pass@host/..." shape, mask everything after the first ':'.
    masked = re.sub(r"//([^/@:]+):([^@/]*)@", r"//\1:***@", uri)
    return masked if masked else "<hidden>"


def get_mongodb_uri() -> str:
    """Return the MongoDB connection string from MONGODB_URI (whitespace trimmed)."""
    logger.info("Loading `MONGODB_URI` from environment")
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        logger.error("`MONGODB_URI` is missing (check your `.env` file)")
        raise ValueError("MONGODB_URI is not set in the environment or .env file")
    logger.info("`MONGODB_URI` loaded successfully")
    return uri


def connect_mongodb(uri: Optional[str] = None) -> MongoClient:
    """
    Establish a MongoDB client using the given URI or MONGODB_URI from the environment.

    Reuse the returned client for multiple operations; it manages a connection pool.
    """
    logger.info("Starting MongoDB connection")
    connection_uri = (uri or get_mongodb_uri()).strip()
    if not connection_uri:
        raise ValueError("MongoDB URI is empty")
    logger.info(f"Using MongoDB URI: {_mask_mongodb_uri(connection_uri)}")

    try:
        client = MongoClient(connection_uri)
        # Force server selection so connection/auth problems surface early.
        client.admin.command("ping")
        logger.info("MongoDB connection established")
        return client
    except (PyMongoError, Exception):
        logger.exception("MongoDB connection failed")
        raise
