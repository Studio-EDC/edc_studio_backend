from typing import List
from fastapi import APIRouter, HTTPException
from app.models.asset import Asset
from app.services.assets_service import (
    create_asset,
    get_all_assets,
    get_asset_by_id,
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


@router.get("/")
async def list_assets():
    return await get_all_assets()


@router.get("/by-edc/{edc_id}", response_model=List[Asset])
async def list_assets_by_edc(edc_id: str):
    return await get_assets_by_edc_id(edc_id)


@router.get("/by-asset-id/{edc_id}/{asset_id}", response_model=Asset)
async def get_asset_by_asset_id(edc_id: str, asset_id: str):
    return await get_asset_by_asset_id_service(edc_id, asset_id)


@router.get("/{id}")
async def get_asset(id: str):
    try:
        asset = await get_asset_by_id(id)
        return asset
    except ValueError:
        raise HTTPException(status_code=404, detail="Asset not found")


@router.put("/{edc_id}")
async def update_asset_route(asset: Asset, edc_id: str):
    success = await update_asset(asset, edc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found or not updated")
    return {"message": "Asset updated successfully"}


@router.delete("/{asset_id}/{edc_id}")
async def delete_asset_route(asset_id: str, edc_id: str):
    success = await delete_asset(asset_id, edc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found or not deleted")
    return {"message": "Asset deleted successfully"}

