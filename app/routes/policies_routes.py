from fastapi import APIRouter, HTTPException
from app.models.policy import Policy
from app.services.policies_service import create_policy, delete_policy, get_policies_by_edc_id, get_policy_by_policy_id_service

router = APIRouter()


@router.post("/", status_code=201)
async def create_policy_route(data: Policy):
    inserted_id = await create_policy(data)
    return inserted_id['@id']


@router.get("/by-edc/{edc_id}", response_model=list[Policy])
async def list_policies_by_edc(edc_id: str):
    return await get_policies_by_edc_id(edc_id)

@router.get("/by-policy-id/{edc_id}/{policy_id}", response_model=Policy)
async def get_policy_by_policy_id(edc_id: str, policy_id: str):
    return await get_policy_by_policy_id_service(edc_id, policy_id)

@router.delete("/{policy_id}/{edc_id}")
async def delete_asset_route(policy_id: str, edc_id: str):
    success = await delete_policy(policy_id, edc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found or not deleted")
    return {"message": "Asset deleted successfully"}
