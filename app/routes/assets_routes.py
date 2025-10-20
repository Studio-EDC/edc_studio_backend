"""
Asset routes.

This module defines the API endpoints related to asset management within
the EDC Studio Backend. Assets represent data resources that can be
published, transferred, or managed through EDC connectors.

Each route provides an asynchronous operation to create, retrieve,
update, or delete assets, interacting with the corresponding
service layer (`app.services.assets_service`).
"""

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


@router.post("", status_code=201)
async def create_asset_route(data: Asset):
    """
    Create a new asset in a specific EDC connector.

    This endpoint registers a new asset in the database and associates
    it with the specified EDC connector. The asset definition includes
    metadata such as name, type, and data address configuration.

    Args:
        data (Asset): The asset data to create.

    Returns:
        str: The identifier (`@id`) of the newly created asset.

    Example:
        >>> POST /assets
        {
            "asset_id": "asset-001",
            "name": "Weather Dataset",
            "content_type": "application/json",
            "data_address_name": "weather-data",
            "data_address_type": "HttpData",
            "data_address_proxy": false,
            "base_url": "https://data.server.com/weather",
            "edc": "edc-provider-01"
        }
    """

    inserted_id = await create_asset(data)
    return inserted_id['@id']


@router.get("/by-edc/{edc_id}", response_model=List[Asset])
async def list_assets_by_edc(edc_id: str):
    """
    Retrieve all assets associated with a specific EDC connector.

    Args:
        edc_id (str): Identifier of the EDC connector.

    Returns:
        List[Asset]: List of assets registered under the given connector.

    Example:
        >>> GET /assets/by-edc/edc-provider-01
    """

    return await get_assets_by_edc_id(edc_id)


@router.get("/by-asset-id/{edc_id}/{asset_id}", response_model=Asset)
async def get_asset_by_asset_id(edc_id: str, asset_id: str):
    """
    Retrieve a specific asset by its ID within a given EDC connector.

    Args:
        edc_id (str): Identifier of the EDC connector.
        asset_id (str): Unique identifier of the asset.

    Returns:
        Asset: The asset matching the given EDC and asset ID.

    Example:
        >>> GET /assets/by-asset-id/edc-provider-01/asset-001
    """

    return await get_asset_by_asset_id_service(edc_id, asset_id)


@router.put("/{edc_id}")
async def update_asset_route(asset: Asset, edc_id: str):
    """
    Update an existing asset within a given EDC connector.

    Args:
        asset (Asset): The updated asset data.
        edc_id (str): Identifier of the EDC connector.

    Returns:
        dict: Confirmation message indicating successful update.

    Example:
        >>> PUT /assets/edc-provider-01
        {
            "asset_id": "asset-001",
            "name": "Updated Weather Dataset",
            ...
        }
    """

    await update_asset(asset, edc_id)
    return {"message": "Asset updated successfully"}


@router.delete("/{asset_id}/{edc_id}")
async def delete_asset_route(asset_id: str, edc_id: str):
    """
    Delete an asset from a specific EDC connector.

    Args:
        asset_id (str): Identifier of the asset to delete.
        edc_id (str): Identifier of the EDC connector.

    Returns:
        dict: Confirmation message indicating successful deletion.

    Example:
        >>> DELETE /assets/asset-001/edc-provider-01
    """
    
    await delete_asset(asset_id, edc_id)
    return {"message": "Asset deleted successfully"}

