import os
from dotenv import load_dotenv
from fastapi import HTTPException
import subprocess
import traceback
from app.models.connector import Connector
from app.db.client import get_db
from pathlib import Path
from app.services.edc_launcher_service import _create_docker_network_if_not_exists, _generate_files, _run_docker_compose, _run_docker_compose_down
from bson import ObjectId
import shutil
from pymongo.results import DeleteResult
import socket

async def create_connector(connector: Connector) -> str:
    db = get_db()
    await check_ports_unique(connector, db)
    connector_dict = connector.dict()
    result = await db["connectors"].insert_one(connector_dict)
    return str(result.inserted_id)

async def check_ports_unique(connector: Connector, db):

    if connector.ports is None:
        return
    
    ports_to_check = [
        connector.ports.http,
        connector.ports.management,
        connector.ports.protocol,
        connector.ports.control,
        connector.ports.public,
        connector.ports.version,
    ]
    
    query = {
        "$or": [
            {f"ports.{field}": port}
            for field, port in zip(["http", "management", "protocol", "control", "public", "version"], ports_to_check)
        ]
    }

    existing = await db["connectors"].find_one(query)
    if existing:
        raise HTTPException(status_code=400, detail="One or more ports are already in use.")
    
    for port in ports_to_check:
        if port is None:
            continue
        if is_port_in_use(port):
            raise HTTPException(status_code=400, detail=f"Port {port} is already in use on this machine.")
        
def is_port_in_use(port: int) -> bool:
    """Check if a given port is currently being used by any process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('127.0.0.1', port))
        return result == 0

async def start_edc_service(connector_id: str):
    db = get_db()
    connector = await db["connectors"].find_one({"_id": ObjectId(connector_id)})
    if not connector:
        raise ValueError("Connector not found")

    base_path = Path("runtime") / str(connector_id)

    try:
        _generate_files(connector, base_path)
        load_dotenv()
        network_name = os.getenv("NETWORK_NAME", "edc-network")
        _create_docker_network_if_not_exists(network_name)
        db_name = 'edc_' + connector['type'] + '_' + str(connector['_id'])
        _run_docker_compose(base_path, db_name)
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
        await db["connectors"].update_one({"_id": ObjectId(connector_id)}, {"$set": {"state": "stopped"}})
    except Exception as e:
        raise RuntimeError(f"Failed to stop connector: {e}")

async def get_all_connectors() -> list[dict]:
    db = get_db()
    connectors = await db["connectors"].find().to_list(length=None)

    try:
        docker_ps_output = subprocess.check_output(
            ["docker", "ps", "--format", "{{.Names}}"], 
            text=True
        )
        active_containers = set(docker_ps_output.strip().splitlines())
    except Exception as e:
        print("⚠️  Docker is not available or not running:")
        traceback.print_exc()
        active_containers = set()

    for c in connectors:
        if c['mode'] == 'managed':
            container_name = f"edc-{c['type']}-{c['_id']}"

            if container_name not in active_containers:
                c['state'] = 'stopped'
            else:
                c['state'] = 'running'

            # Actualiza en la BBDD
            await update_connector(c['_id'], {"state": c['state']})

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
    base_path = Path("runtime") / str(id)

    if not base_path.exists():
        raise ValueError("Runtime folder does not exist")
    
    shutil.rmtree(base_path)

    result: DeleteResult = await db["connectors"].delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise ValueError("Connector not found")
