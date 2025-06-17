from typing import List
from fastapi import APIRouter, HTTPException
from app.models.asset import Asset
from app.services.assets_service import (
    create_asset,
    get_assets_by_edc_id,
    update_asset,
    delete_asset,
    get_asset_by_asset_id_service
)

router = APIRouter()


@router.post("/", status_code=201)
async def create_asset_route(data: Asset):
    inserted_id = await create_asset(data)
    return inserted_id['@id']


@router.get("/by-edc/{edc_id}", response_model=List[Asset])
async def list_assets_by_edc(edc_id: str):
    return await get_assets_by_edc_id(edc_id)


@router.get("/by-asset-id/{edc_id}/{asset_id}", response_model=Asset)
async def get_asset_by_asset_id(edc_id: str, asset_id: str):
    return await get_asset_by_asset_id_service(edc_id, asset_id)


@router.put("/{edc_id}")
async def update_asset_route(asset: Asset, edc_id: str):
    await update_asset(asset, edc_id)
    return {"message": "Asset updated successfully"}


@router.delete("/{asset_id}/{edc_id}")
async def delete_asset_route(asset_id: str, edc_id: str):
    await delete_asset(asset_id, edc_id)
    return {"message": "Asset deleted successfully"}

