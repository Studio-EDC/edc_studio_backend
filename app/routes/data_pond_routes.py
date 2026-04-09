from typing import List, Optional
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
    download_published_file,
    register_published_file,
    upload_user_file,
)

router = APIRouter()


class PublishedFileRegisterRequest(BaseModel):
    filename: str
    display_name: Optional[str] = None

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
    base_url = str(request.base_url).rstrip("/")
    data["url"] = f"{base_url}/published-files/{data['id']}"
    return data


@router.get("/published-files/{published_id}")
async def download_registered_published_file(
    published_id: str,
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
