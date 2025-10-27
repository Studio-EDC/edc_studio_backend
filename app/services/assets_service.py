"""
Assets service.

This module defines the core business logic for managing `Asset` entities
within the EDC Studio Backend. It handles database operations, API requests
to the EDC management endpoints, and validation of connector references.

Each function encapsulates a specific responsibility, such as creating,
updating, deleting, or retrieving assets, both from the internal MongoDB
database and from the EDC connectors via HTTP requests.
"""

from fastapi import HTTPException
from app.db.client import get_db
from bson import ObjectId
from app.models.asset import Asset
import httpx
from app.util.edc_helpers import get_base_url, get_api_key


async def create_asset(data: Asset) -> dict:
    """
    Creates a new asset and registers it with the corresponding EDC connector.

    The function validates the existence of the connector in the database,
    transforms the asset data into the required EDC format, and calls the
    EDC management API to register the asset.

    Args:
        data (Asset): Asset information to be created and registered.

    Returns:
        dict: JSON response from the EDC connector containing the asset ID.

    Raises:
        HTTPException: If the EDC connector is not found or the HTTP request fails.
    """

    db = get_db()
    edc_id = data.edc

    edc = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not edc:
        raise HTTPException(status_code=404, detail="EDC not found")

    asset_dict = data.dict()
    asset_dict["edc"] = ObjectId(edc_id)

    try:
        return await register_asset_with_edc(asset_dict, edc)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from EDC: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Connection error to EDC: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def register_asset_with_edc(asset: dict, connector: dict):
    """
    Registers a new asset directly with the EDC management API.

    Args:
        asset (dict): Asset data in dictionary format.
        connector (dict): Connector configuration retrieved from the database.

    Returns:
        dict: JSON response from the EDC management API.
    """

    base_url = get_base_url(connector, f"/v3/assets")
    api_key = get_api_key(connector)

    payload = {
        "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
        "@id": asset["asset_id"],
        "properties": {
            "name": asset["name"],
            "contenttype": asset["content_type"]
        },
        "dataAddress": {
            "type": asset["data_address_type"],
            "name": asset["data_address_name"],
            "baseUrl": asset["base_url"],
            "proxyPath": str(asset["data_address_proxy"]).lower()
        }
    }

    headers = {"x-api-key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def get_asset_by_asset_id_service(edc_id: str, asset_id: str) -> Asset:
    """
    Retrieves an asset by its ID directly from the EDC connector.

    Args:
        edc_id (str): ID of the EDC connector.
        asset_id (str): Asset identifier within the EDC system.

    Returns:
        Asset: Asset object retrieved from the EDC.

    Raises:
        HTTPException: If the connector is not found or the EDC request fails.
    """

    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/v3/assets/{asset_id}")
    api_key = get_api_key(connector)

    headers = {"x-api-key": api_key}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, headers=headers)
            response.raise_for_status()
            item = response.json()

        return Asset(
            asset_id=item.get("@id"),
            name=item.get("properties", {}).get("name"),
            content_type=item.get("properties", {}).get("contenttype"),
            data_address_name=item.get("dataAddress", {}).get("name"),
            data_address_type=item.get("dataAddress", {}).get("type"),
            data_address_proxy=item.get("dataAddress", {}).get("proxyPath") == "true",
            base_url=item.get("dataAddress", {}).get("baseUrl"),
            edc=edc_id
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from EDC: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Connection error to EDC: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def update_asset(asset: Asset, edc_id: str) -> bool:
    """
    Updates an existing asset in the EDC connector.

    Args:
        asset (Asset): Updated asset data.
        edc_id (str): ID of the EDC connector.

    Returns:
        bool: True if the update succeeded.

    Raises:
        HTTPException: If the connector is not found or the HTTP request fails.
    """

    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/v3/assets/{asset.asset_id}")
    api_key = get_api_key(connector)

    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
            "edc": "https://w3id.org/edc/v0.0.1/ns/",
            "odrl": "http://www.w3.org/ns/odrl/2/"
        },
        "@id": asset.asset_id,
        "@type": "Asset",
        "properties": {
            "name": asset.name,
            "contenttype": asset.content_type
        },
        "dataAddress": {
            "@type": "DataAddress",
            "type": asset.data_address_type,
            "name": asset.data_address_name,
            "baseUrl": asset.base_url,
            "proxyPath": str(asset.data_address_proxy).lower()
        }
    }

    headers = {"x-api-key": api_key}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(base_url, json=payload, headers=headers)
            response.raise_for_status()
            return True
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from EDC: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Connection error to EDC: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def delete_asset(asset_id: str, edc_id: str) -> bool:
    """
    Deletes an asset from the EDC connector.

    Args:
        asset_id (str): Identifier of the asset to delete.
        edc_id (str): Identifier of the EDC connector.

    Returns:
        bool: True if the asset was successfully deleted.

    Raises:
        HTTPException: If the connector is not found or the HTTP request fails.
    """

    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/v3/assets/{asset_id}")
    api_key = get_api_key(connector)

    headers = {"x-api-key": api_key}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(base_url, headers=headers)
            response.raise_for_status()
            return True
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from EDC: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Connection error to EDC: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def get_assets_by_edc_id(edc_id: str) -> list[Asset]:
    """
    Retrieves all assets registered in a specific EDC connector.

    Args:
        edc_id (str): ID of the EDC connector.

    Returns:
        list[Asset]: List of `Asset` objects registered in the EDC.

    Raises:
        HTTPException: If the connector is not found or the HTTP request fails.
    """
    
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, "/v3/assets/request")
    print(base_url)
    api_key = get_api_key(connector)

    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@type": "QuerySpec"
    }

    headers = {"x-api-key": api_key}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        assets = []
        for item in data:
            asset = Asset(
                asset_id=item.get("@id"),
                name=item.get("properties", {}).get("name"),
                content_type=item.get("properties", {}).get("contenttype"),
                data_address_name=item.get("dataAddress", {}).get("name"),
                data_address_type=item.get("dataAddress", {}).get("type"),
                data_address_proxy=item.get("dataAddress", {}).get("proxyPath") == "true",
                base_url=item.get("dataAddress", {}).get("baseUrl"),
                edc=edc_id
            )
            assets.append(asset)

        return assets
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from EDC: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Connection error to EDC: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
