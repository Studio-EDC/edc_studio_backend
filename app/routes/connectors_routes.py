"""
Connector routes.

This module defines the API endpoints used to manage EDC connectors within
the EDC Studio Backend. Each connector can act as a provider or consumer
and supports lifecycle operations such as creation, startup, stop,
update, and deletion.

All routes interact with the connector service layer
(`app.services.connectors_service`) and use Pydantic models for validation.
"""

from fastapi import APIRouter, Body, HTTPException
from app.models.connector import Connector
from app.services.connectors_service import create_connector, delete_connector, start_edc_service, stop_edc_service, get_all_connectors, get_connector_by_id, update_connector
from app.schemas.connector import ConnectorResponse, ConnectorUpdate

router = APIRouter()

@router.post("", status_code=201)
async def create_connector_route(data: Connector):
    """
    Create a new EDC connector.

    Registers a new connector in the database. The connector can later be
    started or stopped through its lifecycle endpoints.

    Args:
        data (Connector): The connector data to be created.

    Returns:
        dict: The identifier of the newly created connector.

    Raises:
        HTTPException: If the connector cannot be created due to a server error.

    Example:
        >>> POST /connectors
        {
            "name": "EDC Provider 01",
            "type": "provider",
            "state": "stopped",
            "mode": "managed"
        }
    """

    inserted_id = await create_connector(data)
    if not inserted_id:
        raise HTTPException(status_code=500, detail="Failed to create connector")
    return {"id": inserted_id}

@router.post("/{id}/start")
async def start_edc(id: str):
    """
    Start an EDC connector.

    Launches the connector process (Docker or local instance) and sets its
    state to `running`.

    Args:
        id (str): Identifier of the connector to start.

    Returns:
        dict: Confirmation message indicating successful start.

    Raises:
        HTTPException:
            - 404: If the connector does not exist.
            - 500: If startup fails unexpectedly.

    Example:
        >>> POST /connectors/edc-provider-01/start
    """

    try:
        await start_edc_service(id)
        return {"message": "Connector started successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start connector: {e}")

@router.post("/{id}/stop")
async def stop_edc(id: str):
    """
    Stop a running EDC connector.

    Gracefully stops a managed connector process and updates its state
    to `stopped`.

    Args:
        id (str): Identifier of the connector to stop.

    Returns:
        dict: Confirmation message indicating successful stop.

    Raises:
        HTTPException:
            - 404: If the connector does not exist.
            - 500: If the stop operation fails.

    Example:
        >>> POST /connectors/edc-provider-01/stop
    """

    try:
        await stop_edc_service(id)
        return {"message": "Connector stopped"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop connector: {e}")

@router.get("", response_model=list[ConnectorResponse])
async def list_connectors():
    """
    Retrieve all registered connectors.

    Returns:
        List[ConnectorResponse]: List of all connectors stored in the system.

    Example:
        >>> GET /connectors
    """

    return await get_all_connectors()

@router.get("/{id}", response_model=ConnectorResponse)
async def get_connector(id: str):
    """
    Retrieve a specific connector by its identifier.

    Args:
        id (str): Identifier of the connector.

    Returns:
        ConnectorResponse: The connector matching the given ID.

    Raises:
        HTTPException: 404 if the connector is not found.

    Example:
        >>> GET /connectors/edc-provider-01
    """

    try:
        connector = await get_connector_by_id(id)
        return ConnectorResponse(**connector)
    except ValueError:
        raise HTTPException(status_code=404, detail="Connector not found")
    
@router.put("/{id}", response_model=dict)
async def update_connector_route(id: str, data: ConnectorUpdate = Body(...)):
    """
    Update a connector's configuration.

    Args:
        id (str): Identifier of the connector to update.
        data (ConnectorUpdate): Fields to be modified.

    Returns:
        dict: Confirmation message indicating successful update.

    Raises:
        HTTPException: 404 if the connector does not exist.

    Example:
        >>> PUT /connectors/edc-provider-01
        {
            "description": "Updated provider connector"
        }
    """

    try:
        await update_connector(id, data.dict(exclude_unset=True))
        return {"message": "Connector updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.delete("/{id}", response_model=dict)
async def delete_connector_route(id: str):
    """
    Delete a connector from the system.

    Args:
        id (str): Identifier of the connector to delete.

    Returns:
        dict: Confirmation message indicating successful deletion.

    Raises:
        HTTPException: 404 if the connector does not exist.

    Example:
        >>> DELETE /connectors/edc-provider-01
    """
    
    try:
        await delete_connector(id)
        return {"message": "Connector deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))