from fastapi import APIRouter
from app.models.contract import Contract
from app.schemas.contract import ContractResponse
from app.services.contracts_service import create_contract, get_contracts_by_edc_id

router = APIRouter()


@router.post("/", status_code=201)
async def create_contract_route(data: Contract):
    inserted_id = await create_contract(data)
    return {"id": inserted_id}


@router.get("/by-edc/{edc_id}", response_model=list[ContractResponse])
async def list_contracts_by_edc(edc_id: str):
    return await get_contracts_by_edc_id(edc_id)