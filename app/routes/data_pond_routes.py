import os
from typing import Any, List, Optional
from fastapi import APIRouter, UploadFile, File
from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.data_pond_service import (
    delete_user_file,
    download_user_file,
    list_user_files,
    list_user_datasets,
    download_published_file,
    register_published_file,
    soft_delete_user_dataset,
    upsert_user_dataset,
    upload_user_file,
)

router = APIRouter()


class PublishedFileRegisterRequest(BaseModel):
    filename: str
    display_name: Optional[str] = None


class DatasetMetadataRequest(BaseModel):
    uid: Optional[str] = None
    dataset_uid: Optional[str] = None
    upcxels_dataset_id: Optional[str] = None
    file_id: Optional[str] = None
    filename: Optional[str] = None
    file_name: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    visible: Optional[bool] = True
    in_datapond: Optional[bool] = True
    published: Optional[bool] = False
    dcat_distribution_json: Optional[Any] = None
    datalake_metadata_json: Optional[Any] = None
    metadata: Optional[dict] = None
    source: Optional[str] = "odoo"


def _payload_dict(payload: BaseModel) -> dict:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_none=True)
    return payload.dict(exclude_none=True)


def _public_base_url(request: Request) -> str:
    configured = (
        os.getenv("EDC_STUDIO_PUBLIC_BASE_URL")
        or os.getenv("API_PUBLIC_BASE_URL")
        or ""
    ).strip()
    if configured:
        return configured.rstrip("/")

    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")

    return str(request.base_url).rstrip("/")

@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    return await upload_user_file(current_user, file)

@router.get("/files/", response_model=List[dict])
async def list_files(
    username: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    return await list_user_files(username, current_user)

@router.get("/files/download/{filename}")
def download_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    response = download_user_file(current_user, filename)
    media_type = response.headers.get("content-type", "application/octet-stream")
    return StreamingResponse(
        response.stream(32 * 1024),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
        background=BackgroundTask(response.close),
    )

@router.delete("/files/{filename}")
def delete_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    return delete_user_file(current_user, filename)


@router.get("/datasets/", response_model=List[dict])
async def list_datasets(
    username: Optional[str] = None,
    include_deleted: bool = False,
    current_user: dict = Depends(get_current_user),
):
    return await list_user_datasets(username, current_user, include_deleted=include_deleted)


@router.post("/datasets/")
async def create_or_update_dataset(
    payload: DatasetMetadataRequest,
    current_user: dict = Depends(get_current_user),
):
    return await upsert_user_dataset(current_user, _payload_dict(payload))


@router.put("/datasets/{uid}")
async def update_dataset(
    uid: str,
    payload: DatasetMetadataRequest,
    current_user: dict = Depends(get_current_user),
):
    return await upsert_user_dataset(current_user, _payload_dict(payload), uid=uid)


@router.delete("/datasets/{uid}")
async def delete_dataset(
    uid: str,
    current_user: dict = Depends(get_current_user),
):
    return await soft_delete_user_dataset(current_user, uid)


@router.post("/published-files/register")
async def register_file_for_publication(
    payload: PublishedFileRegisterRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    data = await register_published_file(
        current_user,
        payload.filename,
        display_name=payload.display_name,
    )
    base_url = _public_base_url(request)
    data["url"] = f"{base_url}/published-files/{data['id']}"
    return data


@router.get("/published-files/{published_id}")
@router.get("/published-files/{published_id}/{_proxy_path:path}")
async def download_registered_published_file(
    published_id: str,
    _proxy_path: str = "",
):
    data = await download_published_file(published_id)
    response = data["response"]
    media_type = data.get("content_type") or "application/octet-stream"
    filename = data.get("filename") or data.get("object_name") or "dataset.bin"
    return StreamingResponse(
        response.stream(32 * 1024),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        background=BackgroundTask(response.close),
    )
