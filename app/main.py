from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import assets_routes, connectors_routes, policies_routes
from app.db.client import init_mongo

app = FastAPI(
    title="EDC Connector Manager",
    description="API to manage Eclipse Data Connectors (EDC)",
    version="0.1.0"
)

# CORS middleware: allow cross-origin requests (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB initialization on startup
@app.on_event("startup")
async def startup_db():
    await init_mongo()

# Register API routers
app.include_router(connectors_routes.router, prefix="/connectors", tags=["Connectors"])
app.include_router(assets_routes.router, prefix="/assets", tags=["Assets"])
app.include_router(policies_routes.router, prefix="/policies", tags=["Policies"])