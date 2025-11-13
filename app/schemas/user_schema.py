from typing import Optional
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    surnames: str
    username: str
    email: EmailStr
    password: str
    is_admin: Optional[bool] = False

class UserOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    is_admin: bool
    name: str
    surnames: str