from __future__ import annotations

import io
import os
from pathlib import PurePosixPath
from typing import Optional
from urllib.parse import urlsplit

from bson import ObjectId
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

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
