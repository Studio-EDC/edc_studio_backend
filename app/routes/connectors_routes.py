from fastapi import APIRouter, Body, HTTPException
from app.models.connector import Connector
from app.services.connectors_service import create_connector, delete_connector, start_edc_service, stop_edc_service, get_all_connectors, get_connector_by_id, update_connector
from app.schemas.connector import ConnectorResponse, ConnectorUpdate

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

@router.get("/{id}", response_model=ConnectorResponse)
async def get_connector(id: str):
    try:
        connector = await get_connector_by_id(id)
        return ConnectorResponse(**connector)
    except ValueError:
        raise HTTPException(status_code=404, detail="Connector not found")
    
@router.put("/{id}", response_model=dict)
async def update_connector_route(id: str, data: ConnectorUpdate = Body(...)):
    try:
        await update_connector(id, data.dict(exclude_unset=True))
        return {"message": "Connector updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.delete("/{id}", response_model=dict)
async def delete_connector_route(id: str):
    try:
        await delete_connector(id)
        return {"message": "Connector deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))