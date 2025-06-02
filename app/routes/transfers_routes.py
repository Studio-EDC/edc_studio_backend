from fastapi import APIRouter, HTTPException
from app.schemas.transfer import RequestCatalog, NegotitateContract, ContractAgreement, StartTransfer, CheckTransfer
from app.services.transfers_service import catalog_request_service, negotiate_contract_service, get_contract_agreement_service, start_http_server_service, stop_http_server_service, start_transfer_service, check_transfer_service

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
