# client.py
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGODB_DB", "edc_backend")

client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None

async def init_mongo():
    global client, _db
    client = AsyncIOMotorClient(MONGO_URI)
    _db = client[MONGO_DB_NAME]
    print(f"✅ Connected to MongoDB at {MONGO_URI}, using database '{MONGO_DB_NAME}'")

def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB was not initialized. Call init_mongo() first.")
    return _db
