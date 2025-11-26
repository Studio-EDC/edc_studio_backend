# Aquí irá la gestión de archivos en el siguiente paso
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Response
import os
from datetime import datetime
from fastapi import HTTPException, Depends

from app.core.security import get_current_user
from app.services.user_service import get_user_by_username

DATA_DIR = "data_pond_storage"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

router = APIRouter()

def get_user_dir(username: str):
    user_dir = os.path.join(DATA_DIR, username)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

@router.post("/files/upload")
def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    user_dir = get_user_dir(current_user.get("username"))
    file_path = os.path.join(user_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(contents)
    return {"filename": file.filename, "size": len(contents)}

@router.get("/files/", response_model=List[dict])
async def list_files(
    username: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    if username:
        user = await get_user_by_username(username)

        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if username != user.get('username') and not current_user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Not allowed")

        target_user = username
    else:
        # Si no hay username, usamos el usuario actual
        target_user = current_user.get("username")

    user_dir = get_user_dir(target_user)
    files = []
    if os.path.exists(user_dir):
        for fname in os.listdir(user_dir):
            fpath = os.path.join(user_dir, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                files.append({
                    "username": target_user,
                    "filename": fname,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
    return files

@router.get("/files/download/{filename}")
def download_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    user_dir = get_user_dir(current_user.get("username"))
    file_path = os.path.join(user_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return Response(
        content=open(file_path, "rb").read(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.delete("/files/{filename}")
def delete_file(
    filename: str,
    current_user: dict = Depends(get_current_user),
):
    user_dir = get_user_dir(current_user.get("username"))
    file_path = os.path.join(user_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(file_path)
    return {"ok": True}