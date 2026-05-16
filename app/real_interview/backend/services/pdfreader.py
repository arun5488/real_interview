import io
import os
import re
from datetime import datetime, timezone
from typing import Any, BinaryIO, Dict, List, Optional, Union

import gridfs
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import CollectionInvalid, PyMongoError
from pypdf import PdfReader

from app.real_interview import logger
from app.real_interview.backend.agents.resume_parse_agent import ResumeParseAgent
from app.real_interview.backend.utils.mongodb import connect_mongodb

load_dotenv()


def _get_db_name() -> str:
    logger.info("inside _get_db_name")
    name = os.getenv("MONGODB_DB_NAME", "").strip()
    if not name:
        raise ValueError("MONGODB_DB_NAME is not set in the environment or .env file")
    return name


def _get_resume_collection_name() -> str:
    logger.info("inside _get_resume_collection_name")
    name = os.getenv("MONGODB_COLLECTION_RESUMES", "").strip()
    if not name:
        raise ValueError(
            "MONGODB_COLLECTION_RESUMES is not set in the environment or .env file"
        )
    return name


def _get_gridfs_bucket() -> str:
    logger.info("inside _get_gridfs_bucket")
    bucket = os.getenv("MONGODB_GRIDFS_RESUME_BUCKET", "").strip()
    return bucket or "resume_pdf_fs"


def _as_user_object_id(userid: Union[str, ObjectId]) -> ObjectId:
    logger.info("inside _as_user_object_id")
    if isinstance(userid, ObjectId):
        return userid
    if not isinstance(userid, str) or not userid.strip():
        raise ValueError("userid must be a non-empty string or ObjectId")
    try:
        return ObjectId(userid.strip())
    except InvalidId as exc:
        raise ValueError("userid is not a valid ObjectId") from exc


def _default_parsed_data() -> Dict[str, Any]:
    logger.info("inside _default_parsed_data")
    return {
        "name": "",
        "email": "",
        "phone": "",
        "education": [],
        "experience": [],
        "skills": [],
        "certifications": [],
    }


def _heuristic_parse(raw_text: str) -> Dict[str, Any]:
    logger.info("inside _heuristic_parse")
    data = _default_parsed_data()
    if not raw_text or not raw_text.strip():
        return data

    text = raw_text.strip()
    email_match = re.search(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text,
    )
    if email_match:
        data["email"] = email_match.group(0)

    phone_match = re.search(
        r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,6}",
        text,
    )
    if phone_match:
        data["phone"] = phone_match.group(0).strip()

    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    if first_line and len(first_line) <= 80 and "@" not in first_line:
        data["name"] = first_line

    return data


def _overlay_scalar_fields(target: Dict[str, Any], overlay: Dict[str, Any]) -> None:
    logger.info("inside _overlay_scalar_fields")
    for key in ("name", "email", "phone"):
        if not (target.get(key) or "").strip() and (overlay.get(key) or "").strip():
            target[key] = overlay[key]


class resume_reader:
    """
    Read resume PDFs, validate uploads, persist binaries in GridFS, and store
    metadata plus extracted text in the resume collection from the environment.
    """

    def __init__(
        self,
        client: Optional[MongoClient] = None,
        parse_agent: Optional[ResumeParseAgent] = None,
    ) -> None:
        logger.info("inside __init__")
        self._owns_client = client is None
        self._client: MongoClient = client or connect_mongodb()
        self._db: Database = self._client[_get_db_name()]
        self._collection_name = _get_resume_collection_name()
        self._gridfs_bucket = _get_gridfs_bucket()
        self._fs = gridfs.GridFS(self._db, collection=self._gridfs_bucket)
        self._parse_agent = parse_agent if parse_agent is not None else ResumeParseAgent()

    def close(self) -> None:
        logger.info("inside close")
        if self._owns_client and self._client is not None:
            self._client.close()

    def _collection(self) -> Collection:
        logger.info("inside _collection")
        return self._db[self._collection_name]

    def ensure_resume_collection(self) -> None:
        logger.info("inside ensure_resume_collection")
        names = set(self._db.list_collection_names())
        if self._collection_name not in names:
            try:
                self._db.create_collection(self._collection_name)
                logger.info(
                    "[resume_reader] created collection %r",
                    self._collection_name,
                )
            except CollectionInvalid:
                logger.warning(
                    "[resume_reader] collection %r already exists (race)",
                    self._collection_name,
                )
        else:
            logger.info(
                "[resume_reader] collection %r already present",
                self._collection_name,
            )

        coll = self._collection()
        coll.create_index([("userid", 1), ("uploaded_ts", -1)], name="userid_uploaded_ts")
        logger.info("[resume_reader] indexes ensured on %r", self._collection_name)

    @staticmethod
    def validate_pdf_file(
        *,
        data: bytes,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> None:
        logger.info("inside validate_pdf_file")
        _ = content_type  # reserved for callers (e.g. Flask); validation uses bytes + filename
        if not data:
            raise ValueError("file size must be greater than zero")
        if filename:
            lower = filename.lower().strip()
            if not lower.endswith(".pdf"):
                raise ValueError("only PDF documents are allowed")
        if not data.startswith(b"%PDF"):
            raise ValueError("only PDF documents are allowed")

    @staticmethod
    def extract_raw_text_from_pdf_bytes(data: bytes) -> str:
        logger.info("inside extract_raw_text_from_pdf_bytes")
        try:
            reader = PdfReader(io.BytesIO(data))
            parts: List[str] = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    parts.append(t)
            return "\n".join(parts).strip()
        except Exception as exc:
            logger.exception("[resume_reader] failed to read PDF")
            raise ValueError("could not read PDF content") from exc

    def save_resume(
        self,
        userid: Union[str, ObjectId],
        data: bytes,
        original_filename: str,
        *,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info("inside save_resume")
        self.validate_pdf_file(data=data, filename=original_filename, content_type=content_type)
        user_oid = _as_user_object_id(userid)

        self.ensure_resume_collection()
        raw_text = self.extract_raw_text_from_pdf_bytes(data)
        parsed_data = self._parse_agent.populate_parsed_data(raw_text)
        _overlay_scalar_fields(parsed_data, _heuristic_parse(raw_text))

        safe_name = os.path.basename(original_filename) or "resume.pdf"
        file_id = self._fs.put(
            data,
            filename=safe_name,
            content_type="application/pdf",
            metadata={"userid": user_oid, "uploaded_ts": datetime.now(timezone.utc)},
        )

        resume_file_ref: Dict[str, str] = {
            "storage": "gridfs",
            "bucket": self._gridfs_bucket,
            "file_id": str(file_id),
            "filename": safe_name,
        }

        uploaded_ts = datetime.now(timezone.utc)
        doc = {
            "userid": user_oid,
            "resume_file": resume_file_ref,
            "raw_text": raw_text,
            "parsed_data": parsed_data,
            "uploaded_ts": uploaded_ts,
        }

        try:
            result = self._collection().insert_one(doc)
        except PyMongoError:
            logger.exception("[resume_reader] insert failed; removing orphaned GridFS file")
            try:
                self._fs.delete(file_id)
            except Exception:
                logger.exception("[resume_reader] failed to delete GridFS file after insert error")
            raise

        out = {
            "_id": str(result.inserted_id),
            "userid": str(user_oid),
            "resume_file": resume_file_ref,
            "raw_text": raw_text,
            "parsed_data": parsed_data,
            "uploaded_ts": uploaded_ts,
        }
        logger.info("[resume_reader] stored resume for user %s", user_oid)
        return out

    def read_pdf_stream(
        self,
        stream: BinaryIO,
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> bytes:
        logger.info("inside read_pdf_stream")
        data = stream.read()
        self.validate_pdf_file(data=data, filename=filename, content_type=content_type)
        return data

    def list_resumes_for_user(self, userid: Union[str, ObjectId]) -> List[Dict[str, Any]]:
        """Return resume summaries for a user, newest upload first."""
        logger.info("inside list_resumes_for_user")
        user_oid = _as_user_object_id(userid)
        self.ensure_resume_collection()
        cursor = (
            self._collection()
            .find(
                {"userid": user_oid},
                {"uploaded_ts": 1, "parsed_data.name": 1, "resume_file.filename": 1},
            )
            .sort("uploaded_ts", -1)
        )
        items: List[Dict[str, Any]] = []
        for doc in cursor:
            ts = doc.get("uploaded_ts")
            parsed = doc.get("parsed_data") or {}
            resume_file = doc.get("resume_file") or {}
            filename = (resume_file.get("filename") or "").strip()
            name = (parsed.get("name") or "").strip() if isinstance(parsed, dict) else ""
            label = filename or name or "Resume"
            uploaded_ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            items.append(
                {
                    "resume_id": str(doc["_id"]),
                    "uploaded_ts": uploaded_ts,
                    "label": label,
                }
            )
        logger.info("[resume_reader] listed %s resume(s) for user %s", len(items), user_oid)
        return items

    def get_resume_for_user(
        self,
        userid: Union[str, ObjectId],
        resume_id: Union[str, ObjectId],
    ) -> Dict[str, Any]:
        """Return one resume document for a user (includes parsed_data)."""
        logger.info("inside get_resume_for_user")
        user_oid = _as_user_object_id(userid)
        resume_oid = _as_user_object_id(resume_id)
        doc = self._collection().find_one(
            {"_id": resume_oid, "userid": user_oid},
            {"raw_text": 0},
        )
        if not doc:
            raise ValueError("resume not found for this user")

        ts = doc.get("uploaded_ts")
        parsed_data = doc.get("parsed_data")
        if not isinstance(parsed_data, dict):
            parsed_data = _default_parsed_data()

        resume_file = doc.get("resume_file") or {}
        filename = (resume_file.get("filename") or "").strip()
        name = (parsed_data.get("name") or "").strip()
        label = filename or name or "Resume"

        return {
            "resume_id": str(doc["_id"]),
            "userid": str(user_oid),
            "uploaded_ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "label": label,
            "parsed_data": parsed_data,
            "resume_file": resume_file,
        }
