"""
Policies Service.

This module provides functionality to manage policy definitions within
the EDC (Eclipse Dataspace Connector) ecosystem. It includes operations
for creating, retrieving, and deleting policies via the connector's
Management API.

These policies define permissions, prohibitions, and obligations
according to the ODRL (Open Digital Rights Language) model and are
essential to enforce access control rules for assets exchanged between
EDC participants.

Handled responsibilities:
    - Policy creation and registration in EDC
    - Conversion between internal models and EDC-compatible JSON-LD
    - Policy retrieval by connector or policy ID
    - Policy deletion from EDC Management API
"""

import json
from fastapi import HTTPException
from app.models.policy import Constraint, Operator, Policy, PolicyDefinition, Rule
from app.db.client import get_db
from bson import ObjectId
from app.util.edc_helpers import get_base_url, get_api_key
import httpx


async def create_policy(data: Policy) -> str:
    """
    Creates and registers a policy definition in a specific EDC connector.

    Args:
        data (Policy): Policy data model containing permissions, prohibitions,
                       and obligations following the ODRL schema.

    Raises:
        HTTPException: If the connector is not found or EDC registration fails.

    Returns:
        str: JSON response from the EDC API confirming the created policy.
    """

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
    """
    Registers a new policy in the EDC Management API.

    Args:
        policy (dict): Dictionary containing the policy data to register.
        connector (dict): EDC connector document containing configuration
                          and API endpoint details.

    Raises:
        httpx.HTTPStatusError: If the EDC Management API returns an error.

    Returns:
        dict: JSON response from the EDC confirming registration.
    """

    base_url = get_base_url(connector, "/v3/policydefinitions")
    api_key = get_api_key(connector)

    payload = convert_policy_to_edc_format(policy)
    headers = {"x-api-key": api_key}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(base_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    except httpx.RequestError as e:
        print(f"❌ [ERROR] Request failed: {e}")
        raise

    except httpx.HTTPStatusError as e:
        print(f"❌ [ERROR] HTTP error: {e.response.status_code}")
        print(f"❌ [ERROR] Response content: {e.response.text}")
        raise


def convert_policy_to_edc_format(policy: dict) -> dict:
    """
    Converts an internal Policy model into EDC-compatible JSON-LD format.

    Args:
        policy (dict): Internal policy representation.

    Returns:
        dict: Policy formatted according to EDC Management API schema.
    """

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
    """
    Converts a list of internal rule objects into EDC ODRL-compliant rules.

    Args:
        rules (list): List of permission, prohibition, or obligation rules.

    Returns:
        list: EDC-compatible rule dictionaries.
    """

    result = []
    for rule in rules:
        converted = {"action": rule["action"].lower()} 

        if "constraint" in rule and rule["constraint"]:
            converted["constraint"] = []
            for c in rule["constraint"]:
                operator = c.get("operator")
                if isinstance(operator, dict) and "id" in operator:
                    operator = operator["id"]
                if isinstance(operator, str):
                    operator = operator.lower()
                    if not operator.startswith("odrl:"):
                        operator = f"odrl:{operator}"  

                converted["constraint"].append({
                    "leftOperand": c["leftOperand"],
                    "operator": {"@id": operator},
                    "rightOperand": c["rightOperand"]
                })

        result.append(converted)
    return result


def normalize_odrl_list(value):
    """
    Ensures that an ODRL property is always returned as a list.

    Args:
        value (Any): Raw ODRL property (dict, list, or None).

    Returns:
        list: A normalized list of elements or an empty list.
    """

    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def convert_rules_get(rule_list):
    """
    Converts a list of ODRL rules from EDC API format to internal Rule models.

    Args:
        rule_list (list): ODRL-formatted rule list from EDC API.

    Returns:
        list[Rule]: List of internal Rule objects.
    """

    result = []
    for r in rule_list:
        constraints = None
        if "odrl:constraint" in r:
            constraints_raw = normalize_odrl_list(r["odrl:constraint"])
            constraints = []
            for c in constraints_raw:
                left = c.get("odrl:leftOperand")
                left = left["@id"] if isinstance(left, dict) else left

                op = c.get("odrl:operator")
                op = op["@id"] if isinstance(op, dict) else op

                right = c.get("odrl:rightOperand")

                constraints.append(Constraint(
                    leftOperand=left.replace("edc:", ""),
                    operator=Operator(id=op.replace("odrl:", "")),
                    rightOperand=right
                ))

        action = r.get("odrl:action", {}).get("@id", "odrl:use")
        action = action.replace("odrl:", "")

        result.append(Rule(
            action=action,
            constraint=constraints
        ))

    return result


async def get_policies_by_edc_id(edc_id: str) -> list[Policy]:
    """
    Retrieves all policy definitions from a given EDC connector.

    Args:
        edc_id (str): ID of the connector from which to retrieve policies.

    Raises:
        HTTPException: If the connector does not exist or communication fails.

    Returns:
        list[Policy]: List of Policy objects retrieved from the EDC.
    """

    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, "/v3/policydefinitions/request")
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
    """
    Retrieves a single policy definition by its ID from an EDC connector.

    Args:
        edc_id (str): EDC connector ID.
        policy_id (str): Unique policy identifier.

    Raises:
        HTTPException: If the connector or policy cannot be found.

    Returns:
        Policy: The corresponding Policy model.
    """

    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/v3/policydefinitions/{policy_id}")
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
    """
    Deletes a policy definition from a specific EDC connector.

    Args:
        policy_id (str): Policy identifier to remove.
        edc_id (str): Connector ID.

    Raises:
        HTTPException: If the connector does not exist or deletion fails.

    Returns:
        bool: True if deletion succeeded, False otherwise.
    """
    
    db = get_db()

    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")

    base_url = get_base_url(connector, f"/v3/policydefinitions/{policy_id}")
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
