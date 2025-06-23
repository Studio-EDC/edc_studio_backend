from fastapi import APIRouter, HTTPException, Header, Response
from fastapi.responses import JSONResponse
from app.models.transfer import Transfer
from app.schemas.transfer import RequestCatalog, NegotitateContract, ContractAgreement, StartTransfer, CheckTransfer
from app.services.transfers_service import catalog_request_service, check_transfer_data_pull_service, get_all_transfers_service, negotiate_contract_service, get_contract_agreement_service, start_http_server_service, start_transfer_service_pull, stop_http_server_service, start_transfer_service, check_transfer_service, create_transfer_service
import requests

router = APIRouter()

@router.post("/catalog_request", status_code=200)
async def catalog_request(data: RequestCatalog):
    try:
        catalog = await catalog_request_service(data.consumer, data.provider)
        return catalog
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch catalog: {str(e)}")
    
@router.post("/negotiate_contract", status_code=200)
async def negotiate_contract(data: NegotitateContract):
    try:
        response = await negotiate_contract_service(data.consumer, data.provider, data.contract_offer_id, data.asset)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to negotiate contract: {str(e)}")
    
@router.post("/contract_agreement", status_code=200)
async def contract_agreement(data: ContractAgreement):
    try:
        response = await get_contract_agreement_service(data.consumer, data.id_contract_negotiation)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get contract agreement: {str(e)}")
    
@router.post("/start_http_server", status_code=200)
async def start_http_server():
    try:
        start_http_server_service() 
        return {"message": "HTTP request logger started successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start HTTP logger: {str(e)}")
    
@router.post("/stop_http_server", status_code=200)
async def stop_http_server():
    try:
        stop_http_server_service() 
        return {"message": "HTTP request logger stopped successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop HTTP logger: {str(e)}")
    
@router.post("/start_transfer", status_code=200)
async def start_transfer(data: StartTransfer):
    try:
        response = await start_transfer_service(data.consumer, data.provider, data.contract_agreement_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start transfer: {str(e)}")
    
@router.post("/check_transfer", status_code=200)
async def check_transfer(data: CheckTransfer):
    try:
        response = await check_transfer_service(data.consumer, data.transfer_process_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check transfer: {str(e)}")
    

@router.post("/", status_code=201)
async def new_transfer(data: Transfer):
    inserted_id = await create_transfer_service(data)
    return {"id": inserted_id}


@router.get("/", status_code=200)
async def get_all_transfers():
    transfers = await get_all_transfers_service()
    return transfers

@router.post("/start_transfer_pull", status_code=200)
async def start_transfer_pull(data: StartTransfer):
    try:
        response = await start_transfer_service_pull(data.consumer, data.provider, data.contract_agreement_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start transfer: {str(e)}")
    
@router.post("/check_data_pull", status_code=200)
async def check_data_pull(data: CheckTransfer):
    try:
        response = await check_transfer_data_pull_service(data.consumer, data.transfer_process_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check data: {str(e)}")
    

@router.get("/proxy_http_logger")
def proxy_http_logger():
    response = requests.get("http://localhost:4000/data")
    data = response.json()
    return JSONResponse(content=data)

@router.get("/proxy_pull")
def proxy_pull(
    uri: str,
    authorization: str = Header(...)
):
    headers = {
        "Authorization": authorization
    }

    r = requests.get(uri, headers=headers)

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=f"Error from pull endpoint: {r.text}")

    content_type = r.headers.get("Content-Type", "application/octet-stream")
    return Response(content=r.content, media_type=content_type)
