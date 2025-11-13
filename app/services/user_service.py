from fastapi import HTTPException
from bson import ObjectId
from app.db.client import get_db
from app.core.security import create_access_token, hash_password, verify_password

async def create_user(user_data):
    db = get_db()
    existing = await db["users"].find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = {
        "name": user_data.name,
        "surnames": user_data.surnames,
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": hash_password(user_data.password),
        "is_admin": False
    }
    result = await db["users"].insert_one(new_user)
    return str(result.inserted_id)

async def get_user_by_email(email: str):
    db = get_db()
    return await db["users"].find_one({"email": email})

async def get_user_by_username(username: str):
    db = get_db()
    return await db["users"].find_one({"username": username})

async def get_user_by_id(user_id: str):
    db = get_db()
    return await db["users"].find_one({"_id": ObjectId(user_id)})

async def authenticate_user(username: str, password: str):
    user = await get_user_by_username(username)
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer"}

async def list_users():
    db = get_db()
    users = await db["users"].find().to_list(100)
    return users

async def get_user_by_id(user_id: str):
    db = get_db()
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def update_user(user_id: str, user_data):
    db = get_db()
    existing = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = {
        "username": user_data.username,
        "hashed_password": hash_password(user_data.password),
        "is_admin": user_data.is_admin,
    }
    await db["users"].update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    return await db["users"].find_one({"_id": ObjectId(user_id)})

async def delete_user(user_id: str):
    db = get_db()
    result = await db["users"].delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}

async def get_user_by_email(email: str):
    db = get_db()
    return await db["users"].find_one({"email": email})
