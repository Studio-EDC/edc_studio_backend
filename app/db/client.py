"""
MongoDB client initialization and access utilities.

This module configures and manages the asynchronous MongoDB client
used across the EDC Studio Backend. It connects to the database using
Motor (the async MongoDB driver for Python) and exposes a global client
and database instance for use in other modules.

Environment variables:
    - MONGODB_URI: Full MongoDB connection string (default: mongodb://localhost:27017)
    - MONGODB_DB:  Database name (default: edc_backend)

Usage example:
    >>> from app.db.client import init_mongo, get_db
    >>> await init_mongo()
    >>> db = get_db()
    >>> print(await db.list_collection_names())
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGODB_DB", "edc_backend")

# Global MongoDB client and database references
client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None

# ------------------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------------------

async def init_mongo():
    """
    Initialize the global MongoDB client and database connection.

    This function connects to the MongoDB server using the connection string
    defined in the environment variables. It should be called once during
    application startup (e.g., in `main.py`).

    Raises:
        Exception: If the connection to MongoDB fails.

    Example:
        >>> await init_mongo()
        ✅ Connected to MongoDB at mongodb://localhost:27017, using database 'edc_backend'
    """
    global client, _db
    client = AsyncIOMotorClient(MONGO_URI)
    _db = client[MONGO_DB_NAME]
    print(f"✅ Connected to MongoDB at {MONGO_URI}, using database '{MONGO_DB_NAME}'")

# ------------------------------------------------------------------------------
# Database Access
# ------------------------------------------------------------------------------

def get_db() -> AsyncIOMotorDatabase:
    """
    Retrieve the initialized MongoDB database instance.

    Returns:
        AsyncIOMotorDatabase: The connected MongoDB database instance.

    Raises:
        RuntimeError: If the database has not been initialized yet
        (i.e., `init_mongo()` has not been called).

    Example:
        >>> db = get_db()
        >>> print(await db.list_collection_names())
    """
    
    if _db is None:
        raise RuntimeError("MongoDB was not initialized. Call init_mongo() first.")
    return _db
