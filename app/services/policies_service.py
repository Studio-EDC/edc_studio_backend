from fastapi import HTTPException
from app.models.policy import Constraint, Operator, Policy, PolicyDefinition, Rule
from app.db.client import get_db
from bson import ObjectId
from app.util.edc_helpers import get_base_url, get_api_key
import httpx


async def create_policy(data: Policy) -> str:
    db = get_db()
    edc_id = data.edc

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    policy_dict = data.model_dump(by_alias=True)
    policy_dict["edc"] = ObjectId(edc_id)

    try:
        return await register_policy_with_edc(policy_dict, connector)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register policy in EDC: {str(e)}")


async def register_policy_with_edc(policy: dict, connector: dict):
    base_url = get_base_url(connector, "/management/v3/policydefinitions")
    api_key = get_api_key(connector)

    payload = convert_policy_to_edc_format(policy)
    headers = {"x-api-key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def convert_policy_to_edc_format(policy: dict) -> dict:
    return {
        "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
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
        converted = {"action": rule["action"]}
        if "constraint" in rule and rule["constraint"]:
            converted["constraint"] = [
                {
                    "leftOperand": c["leftOperand"],
                    "operator": {"@id": c["operator"]["id"]},
                    "rightOperand": c["rightOperand"]
                } for c in rule["constraint"]
            ]
        result.append(converted)
    return result


def normalize_odrl_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def convert_rules_get(rule_list):
    result = []
    for r in rule_list:
        constraints = None
        if "odrl:constraint" in r:
            constraints_raw = normalize_odrl_list(r["odrl:constraint"])
            constraints = [
                Constraint(
                    leftOperand=c["odrl:leftOperand"]["@id"],
                    operator=Operator(id=c["odrl:operator"]["@id"]),
                    rightOperand=c["odrl:rightOperand"]
                ) for c in constraints_raw
            ]
        result.append(Rule(
            action=r["odrl:action"]["@id"].replace("edc:", ""),
            constraint=constraints
        ))
    return result


async def get_policies_by_edc_id(edc_id: str) -> list[Policy]:
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, "/management/v3/policydefinitions/request")
    api_key = get_api_key(connector)

    payload = {
        "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
        "@type": "QuerySpec"
    }
    headers = {"x-api-key": api_key}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        policies = []
        for item in data:
            policy_data = item.get("policy", {})
            policies.append(Policy(
                edc=edc_id,
                policy_id=item.get("@id"),
                policy=PolicyDefinition(
                    type=policy_data.get("@type", "odrl:Set").replace("odrl:", ""),
                    permission=convert_rules_get(normalize_odrl_list(policy_data.get("odrl:permission"))),
                    prohibition=convert_rules_get(normalize_odrl_list(policy_data.get("odrl:prohibition"))),
                    obligation=convert_rules_get(normalize_odrl_list(policy_data.get("odrl:obligation"))),
                    context=policy_data.get("@context", "http://www.w3.org/ns/odrl.jsonld")
                ),
                context=item.get("@context", {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"})
            ))

        return policies

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from EDC: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Connection error to EDC: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def get_policy_by_policy_id_service(edc_id: str, policy_id: str) -> Policy:
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/management/v3/policydefinitions/{policy_id}")
    api_key = get_api_key(connector)

    headers = {"x-api-key": api_key}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, headers=headers)
            response.raise_for_status()
            item = response.json()

        policy_data = item.get("policy", {})

        return Policy(
            edc=edc_id,
            policy_id=item.get("@id"),
            policy=PolicyDefinition(
                type=policy_data.get("@type", "Set").replace("odrl:", ""),
                permission=convert_rules_get(normalize_odrl_list(policy_data.get("odrl:permission"))),
                prohibition=convert_rules_get(normalize_odrl_list(policy_data.get("odrl:prohibition"))),
                obligation=convert_rules_get(normalize_odrl_list(policy_data.get("odrl:obligation"))),
                context=policy_data.get("@context", "http://www.w3.org/ns/odrl.jsonld")
            ),
            context=item.get("@context", {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"})
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from EDC: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Connection error to EDC: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def delete_policy(policy_id: str, edc_id: str) -> bool:
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/management/v3/policydefinitions/{policy_id}")
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
