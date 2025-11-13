"""
EDC Studio Backend — FastAPI application entry point.

This module initializes the FastAPI application that manages
Eclipse Data Connectors (EDC). It configures CORS, connects to MongoDB,
and registers all API routes related to connectors, assets, policies,
contracts, and transfers.

The API acts as a centralized controller for EDC connector management.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.security import hash_password
from app.routes import assets_routes, auth_routes, connectors_routes, contracts_routes, policies_routes, transfers_routes, user_routes
from app.db.client import get_db, init_mongo

# ------------------------------------------------------------------------------
# Application initialization
# ------------------------------------------------------------------------------

app = FastAPI(
    title="EDC Connector Manager",
    description="API to manage Eclipse Data Connectors (EDC)",
    version="0.3.13"
)

# ------------------------------------------------------------------------------
# Middleware configuration
# ------------------------------------------------------------------------------

# CORS middleware: allows cross-origin requests.
# Adjust 'allow_origins' for production deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# Application startup events
# ------------------------------------------------------------------------------

@app.on_event("startup")
async def startup_db():
    """
    Initialize the MongoDB client on application startup.

    This ensures that the database connection is ready before handling requests.
    """
    await init_mongo()

    db = get_db()
    existing = await db["users"].find_one({"username": "admin"})
    if not existing:
        admin_user = {
            "username": "admin",
            "hashed_password": hash_password("admin"),
            "is_admin": True,
        }
        await db["users"].insert_one(admin_user)
        print("✅ Default admin user created: username=admin password=admin")
    else:
        print("ℹ️ Default admin user already exists.")

# ------------------------------------------------------------------------------
# API routes registration
# ------------------------------------------------------------------------------

app.include_router(connectors_routes.router, prefix="/connectors", tags=["Connectors"])
app.include_router(assets_routes.router, prefix="/assets", tags=["Assets"])
app.include_router(policies_routes.router, prefix="/policies", tags=["Policies"])
app.include_router(contracts_routes.router, prefix="/contracts", tags=["Contracts"])
app.include_router(transfers_routes.router, prefix="/transfers", tags=["Transfers"])
app.include_router(auth_routes.router, prefix="", tags=["Auth"])
app.include_router(user_routes.router, prefix="/users", tags=["Users"])