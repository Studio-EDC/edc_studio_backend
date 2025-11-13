from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.schemas.user_schema import UserCreate
from app.services.user_service import authenticate_user, create_user

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/token")
async def login(request: LoginRequest):
    return await authenticate_user(request.username, request.password)

@router.post("/register", status_code=201)
async def register_user(user: UserCreate):
    user_id = await create_user(user)
    return {"message": "User created", "id": user_id}