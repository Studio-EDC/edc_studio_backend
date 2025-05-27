from fastapi import APIRouter, HTTPException
from app.models.policy import Policy
from app.schemas.policy import PolicyResponse
from app.services.policies_service import create_policy, get_policies_by_edc_id

router = APIRouter()


@router.post("/", status_code=201)
async def create_policy_route(data: Policy):
    inserted_id = await create_policy(data)
    return {"id": inserted_id}


@router.get("/by-edc/{edc_id}", response_model=list[PolicyResponse])
async def list_policies_by_edc(edc_id: str):
    return await get_policies_by_edc_id(edc_id)