from fastapi import HTTPException
from app.db.client import get_db
from bson import ObjectId
from app.models.asset import Asset
import httpx


async def create_asset(data: Asset) -> str:
    db = get_db()
    edc_id = data.edc

    # Check if EDC exists
    edc = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not edc:
        raise HTTPException(status_code=404, detail="EDC not found")

    asset_dict = data.dict()
    asset_dict["edc"] = ObjectId(edc_id)

    result = await db["assets"].insert_one(asset_dict)

    # Register asset in EDC
    try:
        await register_asset_with_edc(asset_dict, edc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register asset in EDC: {str(e)}")

    return str(result.inserted_id)


async def register_asset_with_edc(asset: dict, connector: dict):
    if connector["mode"] == "managed":
        management_port = connector["ports"]["management"]
        base_url = f"http://localhost:{management_port}/management/v3/assets"
    elif connector["mode"] == "remote":
        base_url = f"{connector['endpoints_url']['management'].rstrip('/')}/management/v3/assets"
    else:
        raise ValueError("Invalid connector mode")

    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
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

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload)
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
        raise ValueError("Asset not found")
    asset["id"] = str(asset["_id"])
    del asset["_id"]
    return asset

async def get_asset_by_asset_id(asset_id: str) -> dict:
    db = get_db()
    asset = await db["assets"].find_one({"asset_id": asset_id})
    if not asset:
        raise ValueError("Asset not found")
    asset["id"] = str(asset["_id"])
    del asset["_id"]
    return asset


async def update_asset(asset_id: str, updated_data: dict) -> bool:
    db = get_db()
    result = await db["assets"].update_one(
        {"_id": ObjectId(asset_id)}, {"$set": updated_data}
    )
    return result.modified_count > 0


async def delete_asset(asset_id: str) -> bool:
    db = get_db()
    result = await db["assets"].delete_one({"_id": ObjectId(asset_id)})
    return result.deleted_count > 0


async def get_assets_by_edc_id(edc_id: str) -> list[dict]:
    db = get_db()
    assets = await db["assets"].find({"edc": ObjectId(edc_id)}).to_list(length=None)

    for asset in assets:
        asset["id"] = str(asset["_id"])
        asset["edc"] = str(asset["edc"])
        del asset["_id"]

    return assets
