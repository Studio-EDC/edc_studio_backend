from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId

class User(BaseModel):
    id: Optional[str] = Field(alias="_id", default=None)
    username: str
    email: str
    hashed_password: str
    is_admin: bool = False
    name: str
    surnames: str
    