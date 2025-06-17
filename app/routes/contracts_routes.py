from fastapi import APIRouter, HTTPException
from app.models.contract import Contract
from app.services.contracts_service import create_contract, delete_contract, get_contract_by_contract_id_service, get_contracts_by_edc_id, update_contract

router = APIRouter()


@router.post("/", status_code=201)
async def create_contract_route(data: Contract):
    inserted_id = await create_contract(data)
    return inserted_id['@id']


@router.get("/by-edc/{edc_id}", response_model=list[Contract])
async def list_contracts_by_edc(edc_id: str):
    return await get_contracts_by_edc_id(edc_id)


@router.get("/by-contract-id/{edc_id}/{contract_id}", response_model=Contract)
async def get_contract_by_contract_id(edc_id: str, contract_id: str):
    return await get_contract_by_contract_id_service(edc_id, contract_id)


@router.put("/{edc_id}")
async def update_contract_route(contract: Contract, edc_id: str):
    success = await update_contract(contract, edc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found or not updated")
    return {"message": "Asset updated successfully"}


@router.delete("/{contract_id}/{edc_id}")
async def delete_contract_route(contract_id: str, edc_id: str):
    success = await delete_contract(contract_id, edc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found or not deleted")
    return {"message": "Asset deleted successfully"}