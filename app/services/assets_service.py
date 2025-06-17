from fastapi import HTTPException
from app.db.client import get_db
from bson import ObjectId
from app.models.asset import Asset
import httpx
from app.util.edc_helpers import get_base_url, get_api_key


async def create_asset(data: Asset) -> dict:
    db = get_db()
    edc_id = data.edc

    edc = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not edc:
        raise HTTPException(status_code=404, detail="EDC not found")

    asset_dict = data.dict()
    asset_dict["edc"] = ObjectId(edc_id)

    try:
        return await register_asset_with_edc(asset_dict, edc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register asset in EDC: {str(e)}")


async def register_asset_with_edc(asset: dict, connector: dict):
    base_url = get_base_url(connector, f"/management/v3/assets")
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


async def get_all_assets() -> list[dict]:
    db = get_db()
    assets = await db["assets"].find().to_list(length=None)
    for a in assets:
        a["id"] = str(a["_id"])
        del a["_id"]
    return assets


async def get_asset_by_id(asset_id: str) -> dict:
    db = get_db()
    asset = await db["assets"].find_one({"_id": ObjectId(asset_id)})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset["id"] = str(asset["_id"])
    del asset["_id"]
    return asset


async def get_asset_by_asset_id_service(edc_id: str, asset_id: str) -> Asset:
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/management/v3/assets/{asset_id}")
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
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/management/v3/assets/{asset.asset_id}")
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
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/management/v3/assets/{asset_id}")
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
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, "/management/v3/assets/request")
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
