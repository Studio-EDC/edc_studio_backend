"""
Transfer routes.

This module defines the API endpoints responsible for managing
data transfers between EDC connectors in the EDC Studio Backend.
Transfers can follow both push and pull models, with full
support for contract negotiation, catalog retrieval, and
data flow monitoring.

All endpoints interact with the EDC connectors via the service layer
(`app.services.transfers_service`) and facilitate end-to-end
data exchange orchestration.
"""

import os
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Header, Response
from fastapi.responses import JSONResponse
from app.models.transfer import Transfer
from app.schemas.transfer import RequestCatalog, NegotitateContract, ContractAgreement, StartTransfer, CheckTransfer
from app.services.transfers_service import catalog_request_service, check_transfer_data_pull_service, get_all_transfers_service, negotiate_contract_service, get_contract_agreement_service, start_http_server_service, start_transfer_service_pull, stop_http_server_service, start_transfer_service, check_transfer_service, create_transfer_service
import requests

router = APIRouter()

@router.post("/catalog_request", status_code=200)
async def catalog_request(data: RequestCatalog):
    """
    Request the data catalog from a provider connector.

    Args:
        data (RequestCatalog): Contains consumer and provider identifiers.

    Returns:
        dict: The catalog data returned by the provider connector.

    Raises:
        HTTPException:
            - 404: If the provider connector is not found.
            - 500: If the catalog request fails.

    Example:
        >>> POST /transfers/catalog_request
        {
            "consumer": "edc-consumer-01",
            "provider": "edc-provider-01"
        }
    """

    try:
        catalog = await catalog_request_service(data.consumer, data.provider)
        return catalog
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch catalog: {str(e)}")
    
@router.post("/negotiate_contract", status_code=200)
async def negotiate_contract(data: NegotitateContract):
    """
    Negotiate a data-sharing contract between consumer and provider connectors.

    Args:
        data (NegotitateContract): Contains consumer, provider, contract offer ID,
            and associated asset.

    Returns:
        dict: Contract negotiation response from the EDC provider.

    Raises:
        HTTPException:
            - 404: If the connectors or contract offer are not found.
            - 500: If negotiation fails.

    Example:
        >>> POST /transfers/negotiate_contract
        {
            "consumer": "edc-consumer-01",
            "provider": "edc-provider-01",
            "contract_offer_id": "offer-123",
            "asset": "asset-001"
        }
    """

    try:
        response = await negotiate_contract_service(data.consumer, data.provider, data.contract_offer_id, data.asset)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to negotiate contract: {str(e)}")
    
@router.post("/contract_agreement", status_code=200)
async def contract_agreement(data: ContractAgreement):
    """
    Retrieve the contract agreement details for a specific negotiation.

    Args:
        data (ContractAgreement): Contains consumer ID and contract negotiation ID.

    Returns:
        dict: Contract agreement details.

    Raises:
        HTTPException:
            - 404: If the contract negotiation ID is invalid.
            - 500: If fetching the agreement fails.

    Example:
        >>> POST /transfers/contract_agreement
        {
            "consumer": "edc-consumer-01",
            "id_contract_negotiation": "negotiation-001"
        }
    """

    try:
        response = await get_contract_agreement_service(data.consumer, data.id_contract_negotiation)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get contract agreement: {str(e)}")
    
@router.post("/start_http_server", status_code=200)
async def start_http_server():
    """
    Start a local HTTP server to log incoming data requests.

    Returns:
        dict: Confirmation message upon successful start.

    Raises:
        HTTPException: 500 if the server cannot be started.
    """

    try:
        start_http_server_service() 
        return {"message": "HTTP request logger started successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start HTTP logger: {str(e)}")
    
@router.post("/stop_http_server", status_code=200)
async def stop_http_server():
    """
    Stop the HTTP server used for logging data transfer requests.

    Returns:
        dict: Confirmation message upon successful stop.

    Raises:
        HTTPException: 500 if stopping the server fails.
    """

    try:
        stop_http_server_service() 
        return {"message": "HTTP request logger stopped successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop HTTP logger: {str(e)}")
    
@router.post("/start_transfer", status_code=200)
async def start_transfer(data: StartTransfer):
    """
    Start a data transfer in push mode.

    Args:
        data (StartTransfer): Contains consumer, provider, and contract agreement ID.

    Returns:
        dict: Transfer process details.

    Raises:
        HTTPException:
            - 404: If connectors or contracts are invalid.
            - 500: If transfer start fails.
    """

    try:
        response = await start_transfer_service(data.consumer, data.provider, data.contract_agreement_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start transfer: {str(e)}")
    
@router.post("/check_transfer", status_code=200)
async def check_transfer(data: CheckTransfer):
    """
    Check the status of an ongoing transfer process.

    Args:
        data (CheckTransfer): Contains consumer and transfer process ID.

    Returns:
        dict: Transfer process state details.

    Raises:
        HTTPException:
            - 404: If the transfer ID is invalid.
            - 500: If status retrieval fails.
    """

    try:
        response = await check_transfer_service(data.consumer, data.transfer_process_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check transfer: {str(e)}")
    

@router.post("", status_code=201)
async def new_transfer(data: Transfer):
    """
    Register a completed transfer in the database.

    Args:
        data (Transfer): Transfer metadata including consumer, provider,
            asset, and process IDs.

    Returns:
        dict: The ID of the newly created transfer record.
    """

    inserted_id = await create_transfer_service(data)
    return {"id": inserted_id}


@router.get("", status_code=200)
async def get_all_transfers():
    """
    Retrieve all registered transfers from the database.

    Returns:
        List[Transfer]: List of all completed transfers.
    """

    transfers = await get_all_transfers_service()
    return transfers

@router.post("/start_transfer_pull", status_code=200)
async def start_transfer_pull(data: StartTransfer):
    """
    Start a data transfer in pull mode.

    Args:
        data (StartTransfer): Contains consumer, provider, and contract agreement ID.

    Returns:
        dict: Transfer process details for pull operation.

    Raises:
        HTTPException:
            - 404: If connectors or contracts are invalid.
            - 500: If transfer start fails.
    """

    try:
        response = await start_transfer_service_pull(data.consumer, data.provider, data.contract_agreement_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start transfer: {str(e)}")
    
@router.post("/check_data_pull", status_code=200)
async def check_data_pull(data: CheckTransfer):
    """
    Check the data availability for pull-based transfers.

    Args:
        data (CheckTransfer): Contains consumer and transfer process ID.

    Returns:
        dict: Pull data status from the provider.
    """

    try:
        response = await check_transfer_data_pull_service(data.consumer, data.transfer_process_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))    

@router.get("/proxy_http_logger")
def proxy_http_logger():
    """
    Proxy endpoint to retrieve logs from the HTTP logger.

    Returns:
        JSONResponse: Logged HTTP requests captured during data transfer.
    """

    load_dotenv()
    
    if os.getenv("TYPE", "localhost") == 'localhost':
        response = requests.get("http://localhost:4000/data")
    else:
        response = requests.get("http://http-logger:4000/data")
    data = response.json()
    return JSONResponse(content=data)

@router.get("/proxy_pull")
def proxy_pull(
    uri: str,
    authorization: str = Header(...)
):
    """
    Proxy endpoint for pull transfers.

    Fetches data directly from the provider using the provided URI
    and authorization header.

    Args:
        uri (str): Data URI to pull from the provider.
        authorization (str): Authorization token header.

    Returns:
        Response: Raw content fetched from the provider.

    Raises:
        HTTPException: If the provider returns an error.
    """
    
    headers = {
        "Authorization": authorization
    }

    r = requests.get(uri, headers=headers)

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=f"Error from pull endpoint: {r.text}")

    content_type = r.headers.get("Content-Type", "application/octet-stream")
    return Response(content=r.content, media_type=content_type)
