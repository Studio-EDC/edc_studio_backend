from fastapi import APIRouter, HTTPException
from app.models.connector import Connector
from app.services.connectors_service import create_connector, start_edc_service, stop_edc_service, get_all_connectors
from app.schemas.connector_read import ConnectorResponse

router = APIRouter()

@router.post("/", status_code=201)
async def create_connector_route(data: Connector):
    inserted_id = await create_connector(data)
    if not inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create connector")
    return {"id": inserted_id}

@router.post("/{id}/start")
async def start_edc(id: str):
    try:
        await start_edc_service(id)
        return {"message": "Connector started successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start connector: {e}")

@router.post("/{id}/stop")
async def stop_edc(id: str):
    try:
        await stop_edc_service(id)
        return {"message": "Connector stopped and runtime deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop connector: {e}")

@router.get("/", response_model=list[ConnectorResponse])
async def list_connectors():
    return await get_all_connectors()

