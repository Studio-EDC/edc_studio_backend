from typing import List, Optional
from fastapi import APIRouter, UploadFile, File
from fastapi import Depends
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.core.security import get_current_user
from app.services.data_pond_service import (
    delete_user_file,
    download_user_file,
    list_user_files,
    upload_user_file,
)

router = APIRouter()

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
