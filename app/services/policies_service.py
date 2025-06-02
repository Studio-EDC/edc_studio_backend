from fastapi import HTTPException
from app.models.policy import Policy
from app.db.client import get_db
from bson import ObjectId
import httpx


async def create_policy(data: Policy) -> str:
    db = get_db()
    edc_id = data.edc

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    policy_dict = data.model_dump(by_alias=True)
    policy_dict["edc"] = ObjectId(edc_id)

    result = await db["policies"].insert_one(policy_dict)

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

    payload = convert_policy_to_edc_format(policy)

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload)
        response.raise_for_status()
        return response.json()
    
def convert_policy_to_edc_format(policy: dict) -> dict:
    return {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
        },
        "@id": policy["policy_id"],
        "policy": {
            "@context": "http://www.w3.org/ns/odrl.jsonld",
            "@type": policy["policy"]["type"],
            "permission": _convert_rules(policy["policy"].get("permission", [])),
            "prohibition": _convert_rules(policy["policy"].get("prohibition", [])),
            "obligation": _convert_rules(policy["policy"].get("obligation", [])),
        }
    }


def _convert_rules(rules: list) -> list:
    result = []
    for rule in rules:
        converted = {
            "action": rule["action"]
        }
        if "constraint" in rule and rule["constraint"]:
            converted["constraint"] = [
                {
                    "leftOperand": c["leftOperand"],
                    "operator": {"@id": c["operator"]["id"]},
                    "rightOperand": c["rightOperand"]
                }
                for c in rule["constraint"]
            ]
        result.append(converted)
    return result


async def get_policies_by_edc_id(edc_id: str) -> list[dict]:
    db = get_db()
    policies = await db["policies"].find({"edc": ObjectId(edc_id)}).to_list(length=None)

    for p in policies:
        p["id"] = str(p["_id"])
        p["edc"] = str(p["edc"])
        del p["_id"]

    return policies