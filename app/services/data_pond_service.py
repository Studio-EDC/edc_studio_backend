from __future__ import annotations

import io
import os
from pathlib import PurePosixPath
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from app.services.user_service import get_user_by_username

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

    if not endpoint or not access_key or not secret_key:
        raise HTTPException(
            status_code=500,
            detail="MinIO is not configured. Set MINIO_ENDPOINT, MINIO_ACCESS_KEY and MINIO_SECRET_KEY.",
        )

    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def _normalize_filename(filename: str) -> str:
    normalized = PurePosixPath(filename).name.strip()
    if not normalized or normalized in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return normalized


def _bucket_name_from_user_id(user_id: str) -> str:
    normalized = str(user_id).strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid user id")
    return normalized


def _serialize_user_id(user: dict) -> str:
    user_id = user.get("_id")
    if isinstance(user_id, ObjectId):
        return str(user_id)
    return str(user_id)


def ensure_user_bucket(user: dict) -> str:
    bucket_name = _bucket_name_from_user_id(_serialize_user_id(user))
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

    return {"bucket": bucket_name, "filename": filename, "size": len(content)}


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
