from fastapi import HTTPException
from app.models.policy import Policy
from app.db.client import get_db
from bson import ObjectId
import httpx


async def create_policy(data: Policy) -> str:
    db = get_db()
    edc_id = data.edc

    # Check if EDC exists
    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    policy_dict = data.dict()
    policy_dict["edc"] = ObjectId(edc_id)

    result = await db["policies"].insert_one(policy_dict)

    # Register policy in EDC
    try:
        await register_policy_with_edc(policy_dict, connector)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register policy in EDC: {str(e)}")

    return str(result.inserted_id)


async def register_policy_with_edc(policy: dict, connector: dict):
    if connector["mode"] == "managed":
        management_port = connector["ports"]["management"]
        base_url = f"http://localhost:{management_port}/management/v3/policydefinitions"
    elif connector["mode"] == "remote":
        base_url = f"{connector['endpoints_url']['management'].rstrip('/')}/management/v3/policydefinitions"
    else:
        raise ValueError("Invalid connector mode")

    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
            "odrl": "http://www.w3.org/ns/odrl/2/"
        },
        "@id": policy["policy"].get("@id", "defaultPolicyId"),
        "policy": policy["policy"]["policy"]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload)
        response.raise_for_status()
        return response.json()


async def get_policies_by_edc_id(edc_id: str) -> list[dict]:
    db = get_db()
    policies = await db["policies"].find({"edc": ObjectId(edc_id)}).to_list(length=None)
    for p in policies:
        p["id"] = str(p["_id"])
        p["edc"] = str(p["edc"])
        del p["_id"]
    return policies