from __future__ import annotations

import io
import os
import uuid
from pathlib import PurePosixPath
from typing import Any, Optional
from urllib.parse import urlsplit
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from app.db.client import get_db
from app.services.user_service import get_user_by_username

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _get_minio_client() -> Minio:
    raw_endpoint = os.getenv("MINIO_ENDPOINT")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    secure_env = os.getenv("MINIO_SECURE")

    if not raw_endpoint or not access_key or not secret_key:
        raise HTTPException(
            status_code=500,
            detail="MinIO is not configured. Set MINIO_ENDPOINT, MINIO_ACCESS_KEY and MINIO_SECRET_KEY.",
        )

    endpoint, secure = _normalize_minio_endpoint(raw_endpoint, secure_env)

    print(f"[DEBUG] MinIO endpoint: '{endpoint}', secure: {secure}")

    try:
        return Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Invalid MinIO configuration: {exc}") from exc


def _normalize_minio_endpoint(raw_endpoint: str, secure_env: Optional[str]) -> tuple[str, bool]:
    endpoint = raw_endpoint.strip()
    secure = secure_env.lower() == "true" if secure_env is not None else False

    if "://" not in endpoint:
        if "/" in endpoint:
            raise HTTPException(
                status_code=500,
                detail="Invalid MINIO_ENDPOINT. Use host:port or a bare hostname without path.",
            )
        return endpoint, secure

    parsed = urlsplit(endpoint)
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise HTTPException(
            status_code=500,
            detail="Invalid MINIO_ENDPOINT. Do not include a path, query string, or fragment.",
        )

    if not parsed.hostname:
        raise HTTPException(status_code=500, detail="Invalid MINIO_ENDPOINT. Host is required.")

    normalized_endpoint = parsed.hostname
    if parsed.port:
        normalized_endpoint = f"{normalized_endpoint}:{parsed.port}"

    if secure_env is None:
        secure = parsed.scheme == "https"

    return normalized_endpoint, secure


def _normalize_filename(filename: str) -> str:
    normalized = PurePosixPath(filename).name.strip()
    if not normalized or normalized in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return normalized


def _normalize_dataset_uid(uid: Optional[str]) -> str:
    value = str(uid or "").strip()
    if not value:
        return uuid.uuid4().hex
    cleaned = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    normalized = "".join(cleaned).strip("-._")
    if not normalized:
        return uuid.uuid4().hex
    return normalized[:128]


def _normalize_state_key(key: Optional[str]) -> str:
    value = str(key or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Invalid state key")
    cleaned = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    normalized = "".join(cleaned).strip("-._")
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid state key")
    return normalized[:128]


def _dataset_payload_value(payload: dict[str, Any], key: str, default: Any = None) -> Any:
    value = payload.get(key, default)
    return default if value is None else value


def _bucket_name_from_username(username: str) -> str:
    normalized = str(username).strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid username")

    sanitized = []
    for char in normalized:
        if char.isalnum() or char == "-":
            sanitized.append(char)
        else:
            sanitized.append("-")

    bucket_name = f"user-{''.join(sanitized).strip('-')}"
    if len(bucket_name) < 3:
        raise HTTPException(status_code=400, detail="Invalid username")
    if len(bucket_name) > 63:
        bucket_name = bucket_name[:63].rstrip("-")

    return bucket_name


def _serialize_user_id(user: dict) -> str:
    user_id = user.get("_id")
    if isinstance(user_id, ObjectId):
        return str(user_id)
    return str(user_id)


def _get_username(user: dict) -> str:
    username = user.get("username")
    if not username:
        raise HTTPException(status_code=400, detail="Invalid username")
    return str(username)


def ensure_user_bucket(user: dict) -> str:
    bucket_name = _bucket_name_from_username(_get_username(user))
    client = _get_minio_client()

    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
    except S3Error as exc:
        raise HTTPException(status_code=502, detail=f"MinIO bucket error: {exc}") from exc

    return bucket_name


async def upload_user_file(user: dict, file: UploadFile) -> dict:
    filename = _normalize_filename(file.filename or "")
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    bucket_name = ensure_user_bucket(user)
    client = _get_minio_client()

    try:
        client.put_object(
            bucket_name=bucket_name,
            object_name=filename,
            data=io.BytesIO(content),
            length=len(content),
            content_type=file.content_type or "application/octet-stream",
        )
    except S3Error as exc:
        raise HTTPException(status_code=502, detail=f"MinIO upload error: {exc}") from exc
    
    public_base = os.getenv("MINIO_PUBLIC_URL", "").rstrip("/")
    public_url = f"{public_base}/{bucket_name}/{filename}" if public_base else None

    return {"bucket": bucket_name, "filename": filename, "size": len(content), "url": public_url}


async def resolve_target_user(username: Optional[str], current_user: dict) -> dict:
    if not username:
        return current_user

    user = await get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if username != current_user.get("username") and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not allowed")

    return user


async def list_user_files(username: Optional[str], current_user: dict) -> list[dict]:
    target_user = await resolve_target_user(username, current_user)
    bucket_name = ensure_user_bucket(target_user)
    client = _get_minio_client()

    try:
        objects = list(client.list_objects(bucket_name, recursive=True))
    except S3Error as exc:
        raise HTTPException(status_code=502, detail=f"MinIO list error: {exc}") from exc

    files = []
    for item in objects:
        files.append(
            {
                "username": target_user.get("username"),
                "user_id": _serialize_user_id(target_user),
                "bucket": bucket_name,
                "filename": item.object_name,
                "size": item.size,
                "modified": item.last_modified.isoformat() if item.last_modified else None,
            }
        )

    return files


async def upsert_user_dataset(user: dict, payload: dict[str, Any], uid: Optional[str] = None) -> dict:
    owner_username = _get_username(user)
    bucket_name = ensure_user_bucket(user)
    now = datetime.now(timezone.utc)
    dataset_uid = _normalize_dataset_uid(uid or payload.get("uid") or payload.get("dataset_uid"))
    filename = str(
        _dataset_payload_value(payload, "file_id")
        or _dataset_payload_value(payload, "filename")
        or ""
    ).strip()

    if filename:
        filename = _normalize_filename(filename)

    record = {
        "uid": dataset_uid,
        "owner_username": owner_username,
        "owner_user_id": _serialize_user_id(user),
        "bucket": bucket_name,
        "file_id": filename or None,
        "filename": filename or None,
        "file_name": str(_dataset_payload_value(payload, "file_name", filename) or filename or "").strip() or None,
        "name": str(_dataset_payload_value(payload, "name", filename) or filename or "").strip() or None,
        "description": _dataset_payload_value(payload, "description"),
        "visible": bool(_dataset_payload_value(payload, "visible", True)),
        "in_datapond": bool(_dataset_payload_value(payload, "in_datapond", bool(filename))),
        "published": bool(_dataset_payload_value(payload, "published", False)),
        "upcxels_dataset_id": _dataset_payload_value(payload, "upcxels_dataset_id", dataset_uid),
        "dcat_distribution_json": _dataset_payload_value(payload, "dcat_distribution_json"),
        "datalake_metadata_json": _dataset_payload_value(payload, "datalake_metadata_json"),
        "metadata": _dataset_payload_value(payload, "metadata", {}) or {},
        "publication": _dataset_payload_value(payload, "publication", {}) or {},
        "source": _dataset_payload_value(payload, "source", "odoo"),
        "active": True,
        "deleted_at": None,
        "updated_at": now,
    }

    db = get_db()
    collection = db["datasets"]
    existing = await collection.find_one({
        "uid": dataset_uid,
        "owner_username": owner_username,
    })

    if existing:
        created_at = existing.get("created_at")
    else:
        created_at = now
    record["created_at"] = created_at

    await collection.update_one(
        {"uid": dataset_uid, "owner_username": owner_username},
        {"$set": record},
        upsert=True,
    )
    return record


async def list_user_datasets(
    username: Optional[str],
    current_user: dict,
    include_deleted: bool = False,
) -> list[dict]:
    target_user = await resolve_target_user(username, current_user)
    owner_username = _get_username(target_user)
    query: dict[str, Any] = {"owner_username": owner_username}
    if not include_deleted:
        query["active"] = {"$ne": False}
        query["deleted_at"] = None

    db = get_db()
    rows = await db["datasets"].find(query).sort("updated_at", -1).to_list(1000)
    for row in rows:
        row.pop("_id", None)
        for key in ("created_at", "updated_at", "deleted_at"):
            if isinstance(row.get(key), datetime):
                row[key] = row[key].isoformat()
    return rows


async def soft_delete_user_dataset(user: dict, uid: str) -> dict:
    owner_username = _get_username(user)
    dataset_uid = _normalize_dataset_uid(uid)
    now = datetime.now(timezone.utc)
    db = get_db()
    result = await db["datasets"].update_one(
        {
            "uid": dataset_uid,
            "owner_username": owner_username,
            "active": {"$ne": False},
        },
        {
            "$set": {
                "active": False,
                "deleted_at": now,
                "updated_at": now,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"ok": True, "uid": dataset_uid}


async def get_user_state(user: dict, key: str) -> dict:
    owner_username = _get_username(user)
    state_key = _normalize_state_key(key)
    row = await get_db()["user_states"].find_one({
        "owner_username": owner_username,
        "key": state_key,
    })
    if not row:
        return {"key": state_key, "payload": {}}

    row.pop("_id", None)
    for date_key in ("created_at", "updated_at"):
        if isinstance(row.get(date_key), datetime):
            row[date_key] = row[date_key].isoformat()
    return row


async def upsert_user_state(user: dict, key: str, payload: dict[str, Any]) -> dict:
    owner_username = _get_username(user)
    now = datetime.now(timezone.utc)
    state_key = _normalize_state_key(key)
    collection = get_db()["user_states"]
    existing = await collection.find_one({
        "owner_username": owner_username,
        "key": state_key,
    })

    record = {
        "owner_username": owner_username,
        "owner_user_id": _serialize_user_id(user),
        "key": state_key,
        "payload": payload or {},
        "created_at": existing.get("created_at") if existing else now,
        "updated_at": now,
    }
    await collection.update_one(
        {"owner_username": owner_username, "key": state_key},
        {"$set": record},
        upsert=True,
    )
    return record


def download_user_file(user: dict, filename: str):
    bucket_name = ensure_user_bucket(user)
    object_name = _normalize_filename(filename)
    client = _get_minio_client()

    try:
        client.stat_object(bucket_name, object_name)
        return client.get_object(bucket_name, object_name)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(status_code=404, detail="File not found") from exc
        raise HTTPException(status_code=502, detail=f"MinIO download error: {exc}") from exc


def delete_user_file(user: dict, filename: str) -> dict:
    bucket_name = ensure_user_bucket(user)
    object_name = _normalize_filename(filename)
    client = _get_minio_client()

    try:
        client.stat_object(bucket_name, object_name)
        client.remove_object(bucket_name, object_name)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(status_code=404, detail="File not found") from exc
        raise HTTPException(status_code=502, detail=f"MinIO delete error: {exc}") from exc

    return {"ok": True}


async def register_published_file(user: dict, filename: str, display_name: Optional[str] = None) -> dict:
    bucket_name = ensure_user_bucket(user)
    object_name = _normalize_filename(filename)
    client = _get_minio_client()

    try:
        client.stat_object(bucket_name, object_name)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(status_code=404, detail="File not found") from exc
        raise HTTPException(status_code=502, detail=f"MinIO stat error: {exc}") from exc

    db = get_db()
    collection = db["published_files"]
    owner_username = _get_username(user)
    now = datetime.now(timezone.utc)

    existing = await collection.find_one({
        "owner_username": owner_username,
        "bucket": bucket_name,
        "object_name": object_name,
    })

    clean_display_name = _normalize_filename(display_name or object_name)
    if existing:
        await collection.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "display_name": clean_display_name,
                    "updated_at": now,
                    "active": True,
                }
            },
        )
        existing["display_name"] = clean_display_name
        existing["active"] = True
        existing["updated_at"] = now
        return {
            "id": existing["published_id"],
            "bucket": bucket_name,
            "filename": object_name,
            "display_name": clean_display_name,
        }

    published_id = uuid.uuid4().hex
    await collection.insert_one({
        "published_id": published_id,
        "owner_user_id": _serialize_user_id(user),
        "owner_username": owner_username,
        "bucket": bucket_name,
        "object_name": object_name,
        "display_name": clean_display_name,
        "active": True,
        "created_at": now,
        "updated_at": now,
    })
    return {
        "id": published_id,
        "bucket": bucket_name,
        "filename": object_name,
        "display_name": clean_display_name,
    }


async def download_published_file(published_id: str) -> dict:
    published_id = (published_id or "").strip()
    if not published_id:
        raise HTTPException(status_code=400, detail="Invalid published file id")

    db = get_db()
    record = await db["published_files"].find_one({
        "published_id": published_id,
        "active": True,
    })
    if not record:
        raise HTTPException(status_code=404, detail="Published file not found")

    bucket_name = record.get("bucket")
    object_name = _normalize_filename(record.get("object_name") or "")
    client = _get_minio_client()

    try:
        stat = client.stat_object(bucket_name, object_name)
        response = client.get_object(bucket_name, object_name)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(status_code=404, detail="File not found") from exc
        raise HTTPException(status_code=502, detail=f"MinIO download error: {exc}") from exc

    return {
        "response": response,
        "content_type": getattr(stat, "content_type", None) or "application/octet-stream",
        "filename": _normalize_filename(record.get("display_name") or object_name),
        "object_name": object_name,
    }
