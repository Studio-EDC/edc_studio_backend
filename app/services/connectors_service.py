from app.models.connector import Connector
from app.db.client import get_db
from pathlib import Path
from app.services.edc_launcher_service import _generate_files, _run_docker_compose, _run_docker_compose_down
from bson import ObjectId
import shutil
from pymongo.results import DeleteResult

async def create_connector(connector: Connector) -> str:
    db = get_db()
    connector_dict = connector.dict()
    result = await db["connectors"].insert_one(connector_dict)
    return str(result.inserted_id)

async def start_edc_service(connector_id: str):
    db = get_db()
    connector = await db["connectors"].find_one({"_id": ObjectId(connector_id)})
    if not connector:
        raise ValueError("Connector not found")

    base_path = Path("runtime") / str(connector_id)

    try:
        _generate_files(connector, base_path)
        _run_docker_compose(base_path)
        await db["connectors"].update_one({"_id": ObjectId(connector_id)}, {"$set": {"state": "running"}})
    except Exception as e:
        raise RuntimeError(f"Failed to start connector: {e}")

async def stop_edc_service(connector_id: str):
    db = get_db()
    base_path = Path("runtime") / str(connector_id)

    if not base_path.exists():
        raise ValueError("Runtime folder does not exist")

    try:
        _run_docker_compose_down(base_path)
        shutil.rmtree(base_path)
        await db["connectors"].update_one({"_id": ObjectId(connector_id)}, {"$set": {"state": "stopped"}})
    except Exception as e:
        raise RuntimeError(f"Failed to stop connector: {e}")

async def get_all_connectors() -> list[dict]:
    db = get_db()
    connectors = await db["connectors"].find().to_list(length=None)

    for c in connectors:
        c["id"] = str(c["_id"]) 
        del c["_id"] 
        
    return connectors

async def get_connector_by_id(id: str) -> dict:
    db = get_db()
    connector = await db["connectors"].find_one({"_id": ObjectId(id)})

    if not connector:
        raise ValueError("Connector not found")

    connector["id"] = str(connector["_id"])
    del connector["_id"]

    return connector

async def update_connector(id: str, update_data: dict):
    db = get_db()
    result = await db["connectors"].update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise ValueError("Connector not found")
    
async def delete_connector(id: str):
    db = get_db()
    result: DeleteResult = await db["connectors"].delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise ValueError("Connector not found")
