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
from urllib.parse import urljoin
from dotenv import load_dotenv
import logging
from fastapi import APIRouter, HTTPException, Header, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from app.models.transfer import Transfer
from app.schemas.transfer import RequestCatalog, NegotitateContract, ContractAgreement, StartTransfer, CheckTransfer
from app.services.transfers_service import catalog_request_service, check_transfer_data_pull_service, get_all_transfers_service, negotiate_contract_service, get_contract_agreement_service, start_http_server_service, start_transfer_service_pull, stop_http_server_service, start_transfer_service, check_transfer_service, create_transfer_service
import requests

router = APIRouter()
logger = logging.getLogger(__name__)


def _authorization_candidates(value: str, auth_type: str = ""):
    raw = (value or "").strip()
    auth_type = (auth_type or "").strip().lower()
    if not raw:
        return []
    candidates = []
    if raw.lower().startswith("bearer "):
        candidates.append(raw)
        bare = raw[7:].strip()
        if bare:
            candidates.append(bare)
    else:
        if auth_type == "bearer":
            candidates.extend([f"Bearer {raw}", raw])
        else:
            candidates.extend([f"Bearer {raw}", raw])

    seen = set()
    deduped = []
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def _request_with_redirects(url: str, headers: dict, *, stream: bool, timeout, max_redirects: int = 5):
    current_url = url
    for _ in range(max_redirects + 1):
        response = requests.get(current_url, headers=headers, stream=stream, timeout=timeout, allow_redirects=False)
        if response.status_code not in (301, 302, 303, 307, 308):
            return response
        location = (response.headers.get("Location") or "").strip()
        if not location:
            return response
        next_url = urljoin(current_url, location)
        try:
            response.close()
        except Exception:
            pass
        current_url = next_url
    return requests.get(current_url, headers=headers, stream=stream, timeout=timeout, allow_redirects=False)

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
    
    last_response = None
    for auth_value in _authorization_candidates(authorization):
        headers = {"Authorization": auth_value}
        r = _request_with_redirects(uri, headers, stream=False, timeout=(10, 600))
        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "application/octet-stream")
            return Response(content=r.content, media_type=content_type)
        last_response = r
        if r.status_code not in (401, 403):
            break

    detail = last_response.text if last_response is not None else "Unknown pull endpoint error"
    status_code = last_response.status_code if last_response is not None else 502
    raise HTTPException(status_code=status_code, detail=f"Error from pull endpoint: {detail}")


@router.get("/download_pull")
async def download_pull(
    consumer: str,
    transfer_process_id: str,
):
    """
    Resolve the current EDR for a pull transfer and stream the data through the backend.

    This avoids exposing internal connector hostnames to external clients such as Odoo.
    """
    try:
        data = await check_transfer_data_pull_service(consumer, transfer_process_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve pull transfer data: {str(e)}")

    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Invalid pull transfer response")

    endpoint = (
        data.get("endpoint")
        or data.get("baseUrl")
        or data.get("endpointUrl")
        or data.get("uri")
        or ""
    ).strip()
    authorization = (
        data.get("authorization")
        or data.get("Authorization")
        or data.get("token")
        or ""
    ).strip()
    auth_type = (data.get("authType") or "").strip()

    if not endpoint or not authorization:
        raise HTTPException(status_code=502, detail="EDR endpoint/token not available")

    logger.info(
        "download_pull resolved EDR for consumer=%s transfer_process_id=%s endpoint=%s",
        consumer,
        transfer_process_id,
        endpoint,
    )

    last_http_error = None
    last_request_error = None
    r = None
    for auth_value in _authorization_candidates(authorization, auth_type=auth_type):
        auth_mode = "bearer" if auth_value.lower().startswith("bearer ") else "raw"
        headers = {"Authorization": auth_value}
        try:
            logger.info(
                "download_pull attempting EDR fetch consumer=%s transfer_process_id=%s endpoint=%s auth_mode=%s",
                consumer,
                transfer_process_id,
                endpoint,
                auth_mode,
            )
            candidate = _request_with_redirects(endpoint, headers, stream=True, timeout=(10, 600))
            if 300 <= candidate.status_code < 400:
                location = (candidate.headers.get("Location") or "").strip()
                logger.warning(
                    "download_pull unresolved redirect for consumer=%s transfer_process_id=%s endpoint=%s status=%s location=%s auth_mode=%s",
                    consumer,
                    transfer_process_id,
                    endpoint,
                    candidate.status_code,
                    location,
                    auth_mode,
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Unresolved redirect from pull endpoint: status={candidate.status_code} location={location or 'n/a'}",
                )
            candidate.raise_for_status()
            r = candidate
            break
        except requests.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else None
            detail = response.text if response is not None else str(exc)
            logger.warning(
                "download_pull HTTP error for consumer=%s transfer_process_id=%s endpoint=%s status=%s auth_mode=%s detail=%s",
                consumer,
                transfer_process_id,
                endpoint,
                status,
                auth_mode,
                detail[:400] if isinstance(detail, str) else detail,
            )
            last_http_error = exc
            try:
                candidate.close()
            except Exception:
                pass
            if status not in (401, 403):
                break
        except HTTPException:
            try:
                candidate.close()
            except Exception:
                pass
            raise
        except requests.RequestException as exc:
            logger.exception(
                "download_pull request error for consumer=%s transfer_process_id=%s endpoint=%s",
                consumer,
                transfer_process_id,
                endpoint,
            )
            last_request_error = exc
            break

    if r is None:
        if last_http_error is not None:
            detail = last_http_error.response.text if last_http_error.response is not None else str(last_http_error)
            raise HTTPException(
                status_code=last_http_error.response.status_code if last_http_error.response is not None else 502,
                detail=detail,
            )
        if last_request_error is not None:
            raise HTTPException(status_code=502, detail=f"Error fetching pull endpoint: {last_request_error}")
        raise HTTPException(status_code=502, detail="Error fetching pull endpoint")

    media_type = r.headers.get("Content-Type", "application/octet-stream")
    response_headers = {}
    content_disposition = (r.headers.get("Content-Disposition") or "").strip()
    if content_disposition:
        response_headers["Content-Disposition"] = content_disposition
    return StreamingResponse(
        r.iter_content(32 * 1024),
        media_type=media_type,
        headers=response_headers,
        background=BackgroundTask(r.close),
    )
