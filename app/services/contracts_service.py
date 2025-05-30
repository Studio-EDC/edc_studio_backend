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
    contract_dict["edc"] = ObjectId(edc_id)

    # Convert accessPolicyId and contractPolicyId to ObjectId
    try:
        contract_dict["accessPolicyId"] = ObjectId(contract_dict["accessPolicyId"])
        contract_dict["contractPolicyId"] = ObjectId(contract_dict["contractPolicyId"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid policy ID format")

    # Convert asset IDs in assetsSelector to ObjectId
    try:
        contract_dict["assetsSelector"] = [ObjectId(aid) for aid in contract_dict.get("assetsSelector", [])]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid asset ID format")

    result = await db["contracts"].insert_one(contract_dict)

    try:
        await register_contract_with_edc(contract_dict, connector)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register contract in EDC: {str(e)}")

    return str(result.inserted_id)


async def register_contract_with_edc(contract: dict, connector: dict):
    if connector["mode"] == "managed":
        management_port = connector["ports"]["management"]
        base_url = f"http://localhost:{management_port}/management/v3/contractdefinitions"
    elif connector["mode"] == "remote":
        base_url = f"{connector['endpoints_url']['management'].rstrip('/')}/management/v3/contractdefinitions"
    else:
        raise ValueError("Invalid connector mode")

    payload = await convert_contract_to_edc_format(contract)

    print(payload)

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload)
        if response.is_error:
            print("Status:", response.status_code)
            print("Response text:", response.text)
        response.raise_for_status()
        return response.json()


async def convert_contract_to_edc_format(contract: dict) -> dict:
    db = get_db()

    asset_selectors = []
    for oid in contract["assetsSelector"]:
        asset = await db["assets"].find_one({"_id": ObjectId(oid)})
        if asset and "asset_id" in asset:
            asset_selectors.append({
                "operandLeft": "asset:prop:id",
                "operator": "=",
                "operandRight": asset["asset_id"]
            })

    access_policy = await db["policies"].find_one({"_id": ObjectId(contract["accessPolicyId"])})
    contract_policy = await db["policies"].find_one({"_id": ObjectId(contract["contractPolicyId"])})

    if not access_policy or not contract_policy:
        raise HTTPException(status_code=404, detail="Access or contract policy not found")

    return {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@id": contract["contract_id"],
        "accessPolicyId": access_policy["policy_id"],
        "contractPolicyId": contract_policy["policy_id"],
        "assetsSelector": asset_selectors
    }


async def get_contracts_by_edc_id(edc_id: str) -> list[dict]:
    db = get_db()
    contracts = await db["contracts"].find({"edc": ObjectId(edc_id)}).to_list(length=None)

    for c in contracts:
        c["id"] = str(c["_id"])
        c["edc"] = str(c["edc"])
        del c["_id"]

        # Convert accessPolicyId
        try:
            access_policy = await db["policies"].find_one({"_id": ObjectId(c["accessPolicyId"])})
            c["accessPolicyId"] = access_policy["policy_id"] if access_policy else None
        except:
            c["accessPolicyId"] = None

        # Convert contractPolicyId
        try:
            contract_policy = await db["policies"].find_one({"_id": ObjectId(c["contractPolicyId"])})
            c["contractPolicyId"] = contract_policy["policy_id"] if contract_policy else None
        except:
            c["contractPolicyId"] = None

        # Convert assetsSelector (lista de ObjectIds)
        converted_assets = []
        for asset_oid in c.get("assetsSelector", []):
            try:
                asset = await db["assets"].find_one({"_id": ObjectId(asset_oid)})
                if asset and "asset_id" in asset:
                    converted_assets.append(asset["asset_id"])
            except:
                continue

        c["assetsSelector"] = converted_assets

    return contracts