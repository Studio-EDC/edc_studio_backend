from fastapi import APIRouter, Depends
from typing import List
from app.schemas.user_schema import UserCreate, UserOut
from app.services import user_service
from app.core.security import get_current_admin

router = APIRouter()

@router.post("/", response_model=UserOut, dependencies=[Depends(get_current_admin)])
async def create_user(user: UserCreate):
    return await user_service.create_user(user)

@router.get("/", response_model=List[UserOut], dependencies=[Depends(get_current_admin)])
async def list_users():
    return await user_service.list_users()

@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(get_current_admin)])
async def get_user(user_id: str):
    return await user_service.get_user_by_id(user_id)

@router.put("/{user_id}", response_model=UserOut, dependencies=[Depends(get_current_admin)])
async def update_user(user_id: str, user: UserCreate):
    return await user_service.update_user(user_id, user)

@router.delete("/{user_id}", dependencies=[Depends(get_current_admin)])
async def delete_user(user_id: str):
    return await user_service.delete_user(user_id)