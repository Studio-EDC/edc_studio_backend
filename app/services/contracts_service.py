from fastapi import HTTPException
from app.models.contract import Contract
from app.db.client import get_db
from bson import ObjectId
import httpx


async def create_contract(data: Contract) -> str:
    db = get_db()
    edc_id = data.edc

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    contract_dict = data.model_dump()

    print(contract_dict)

    try:
        return await register_contract_with_edc(contract_dict, connector)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register contract in EDC: {str(e)}")


async def register_contract_with_edc(contract: dict, connector: dict):
    if connector["mode"] == "managed":
        management_port = connector["ports"]["management"]
        base_url = f"http://localhost:{management_port}/management/v3/contractdefinitions"
    elif connector["mode"] == "remote":
        base_url = f"{connector['endpoints_url']['management'].rstrip('/')}/management/v3/contractdefinitions"
    else:
        raise ValueError("Invalid connector mode")

    payload = await convert_contract_to_edc_format(contract)

    api_key = connector["api_key"]
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")

    headers = {
        "x-api-key": api_key
    }


    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload, headers=headers)
        print(response)
        response.raise_for_status()
        return response.json()


async def convert_contract_to_edc_format(contract: dict) -> dict:

    asset_selectors = []
    for asset_id in contract["assetsSelector"]:
        asset_selectors.append({
            "@type": "https://w3id.org/edc/v0.0.1/ns/Criterion",
            "operandLeft": "id",
            "operator": "=",
            "operandRight": asset_id
        })

    return {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@id": contract["contract_id"],
        "accessPolicyId": contract["accessPolicyId"],
        "contractPolicyId": contract["contractPolicyId"],
        "assetsSelector": asset_selectors
    }


async def get_contracts_by_edc_id(edc_id: str) -> list[dict]:
    db = get_db()

    try:
        connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
        if not connector:
            raise HTTPException(status_code=404, detail="EDC not found")
        
        if connector["mode"] == "managed":
            management_port = connector["ports"]["management"]
            base_url = f"http://localhost:{management_port}/management/v3/contractdefinitions/request"
        elif connector["mode"] == "remote":
            base_url = f"{connector['endpoints_url']['management'].rstrip('/')}/management/v3/contractdefinitions/request"
        else:
            raise ValueError("Invalid connector mode")

        api_key = connector["api_key"]
        if not api_key:
            raise HTTPException(status_code=500, detail="Connector API key not configured")
        
        payload = {
            "@context": {
                "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
            },
            "@type": "QuerySpec"
        }

        headers = {
            "x-api-key": api_key
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(base_url, headers=headers, json=payload)
            response.raise_for_status()
            items = response.json()

        contracts = []

        if isinstance(items, dict):
            items = [items]

        for item in items:
            assets = []
            assets_selector = item.get("assetsSelector")

            if isinstance(assets_selector, dict):
                assets.append(assets_selector.get("operandRight"))
            elif isinstance(assets_selector, list):
                for criterion in assets_selector:
                    assets.append(criterion.get("operandRight"))

            contract = Contract(
                edc=edc_id,
                contract_id=item.get("@id"),
                accessPolicyId=item.get("accessPolicyId"),
                contractPolicyId=item.get("contractPolicyId"),
                assetsSelector=assets,
                context=item.get("@context", {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"})
            )
            contracts.append(contract)

        return contracts

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from EDC: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Connection error to EDC: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")