"""
Contracts service.

This module implements the business logic for managing contract definitions
within the EDC Studio Backend. It handles the interaction between the API,
the MongoDB database, and the EDC Management API for creating, reading,
updating, and deleting contract definitions.

Contracts link assets with access and usage policies to define the conditions
under which data can be exchanged between EDC connectors.
"""

from fastapi import HTTPException
from app.models.contract import Contract
from app.db.client import get_db
from bson import ObjectId
from app.util.edc_helpers import get_base_url, get_api_key
import httpx


async def create_contract(data: Contract) -> str:
    """
    Creates a new contract definition in the EDC system.

    The function retrieves the connector configuration from the database and
    registers the new contract definition via the EDC Management API.

    Args:
        data (Contract): Contract definition data to be created.

    Returns:
        str: JSON response from the EDC Management API.

    Raises:
        HTTPException: If the connector is not found or registration fails.
    """

    edc_id = data.edc
    connector = await _get_connector(edc_id)

    contract_dict = data.model_dump()

    try:
        return await _register_contract_with_edc(contract_dict, connector)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register contract in EDC: {str(e)}")


async def _register_contract_with_edc(contract: dict, connector: dict):
    """
    Registers a contract definition in the EDC Management API.

    Args:
        contract (dict): Contract data to register.
        connector (dict): Connector configuration data.

    Returns:
        dict: Response from the EDC Management API.

    Raises:
        HTTPException: If the EDC returns an error response.
    """

    base_url = get_base_url(connector, "/management/v3/contractdefinitions")
    api_key = get_api_key(connector)

    payload = _convert_contract_to_edc_format(contract)

    headers = {"x-api-key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def _convert_contract_to_edc_format(contract: dict) -> dict:
    """
    Converts a contract from the internal format to the EDC API format.

    Args:
        contract (dict): Internal contract representation.

    Returns:
        dict: Contract formatted according to the EDC Management API specification.
    """

    asset_selectors = [
        {
            "@type": "https://w3id.org/edc/v0.0.1/ns/Criterion",
            "operandLeft": "id",
            "operator": "=",
            "operandRight": asset_id
        }
        for asset_id in contract["assetsSelector"]
    ]

    return {
        "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
        "@id": contract["contract_id"],
        "accessPolicyId": contract["accessPolicyId"],
        "contractPolicyId": contract["contractPolicyId"],
        "assetsSelector": asset_selectors
    }


async def get_contracts_by_edc_id(edc_id: str) -> list[Contract]:
    """
    Retrieves all contract definitions from a given EDC connector.

    Args:
        edc_id (str): MongoDB ID of the connector.

    Returns:
        list[Contract]: List of contract definitions available in the connector.

    Raises:
        HTTPException: If the connector is not found or communication fails.
    """

    connector = await _get_connector(edc_id)

    base_url = get_base_url(connector, "/management/v3/contractdefinitions/request")
    api_key = get_api_key(connector)

    payload = {
        "@context": {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
        "@type": "QuerySpec"
    }
    headers = {"x-api-key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, json=payload, headers=headers)
        response.raise_for_status()
        items = response.json()

    if isinstance(items, dict):
        items = [items]

    contracts = [_parse_contract_item(item, edc_id) for item in items]
    return contracts


async def get_contract_by_contract_id_service(edc_id: str, contract_id: str) -> Contract:
    """
    Retrieves a single contract definition by its ID.

    Args:
        edc_id (str): Connector MongoDB ID.
        contract_id (str): Contract definition ID in the EDC system.

    Returns:
        Contract: Parsed contract object.

    Raises:
        HTTPException: If the connector or contract cannot be found.
    """

    connector = await _get_connector(edc_id)

    base_url = get_base_url(connector, f"/management/v3/contractdefinitions/{contract_id}")
    api_key = get_api_key(connector)
    headers = {"x-api-key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.get(base_url, headers=headers)
        response.raise_for_status()
        item = response.json()

    return _parse_contract_item(item, edc_id)


async def update_contract(contract: Contract, edc_id: str) -> bool:
    """
    Updates an existing contract definition in the EDC system.

    Args:
        contract (Contract): Contract data to update.
        edc_id (str): MongoDB ID of the connector.

    Returns:
        bool: True if the update succeeded, False otherwise.
    """

    connector = await _get_connector(edc_id)

    base_url = get_base_url(connector, "/management/v3/contractdefinitions")
    api_key = get_api_key(connector)

    payload = {
        "@id": contract.contract_id,
        "@type": "ContractDefinition",
        "accessPolicyId": contract.accessPolicyId,
        "contractPolicyId": contract.contractPolicyId,
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
            "edc": "https://w3id.org/edc/v0.0.1/ns/",
            "odrl": "http://www.w3.org/ns/odrl/2/"
        }
    }

    if len(contract.assetsSelector) == 1:
        payload["assetsSelector"] = {
            "@type": "Criterion",
            "operandLeft": "id",
            "operator": "=",
            "operandRight": contract.assetsSelector[0]
        }
    elif len(contract.assetsSelector) > 1:
        payload["assetsSelector"] = [
            {
                "@type": "Criterion",
                "operandLeft": "id",
                "operator": "=",
                "operandRight": asset
            }
            for asset in contract.assetsSelector
        ]

    headers = {"x-api-key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.put(base_url, json=payload, headers=headers)
        if response.status_code == 204:
            return True
        return False


async def delete_contract(contract_id: str, edc_id: str) -> bool:
    """
    Deletes a contract definition from the EDC system.

    Args:
        contract_id (str): Contract ID to delete.
        edc_id (str): MongoDB ID of the connector.

    Returns:
        bool: True if deletion succeeded, False otherwise.
    """

    connector = await _get_connector(edc_id)

    base_url = get_base_url(connector, f"/management/v3/contractdefinitions/{contract_id}")
    api_key = get_api_key(connector)
    headers = {"x-api-key": api_key}

    async with httpx.AsyncClient() as client:
        response = await client.delete(base_url, headers=headers)
        if response.status_code == 204:
            return True
        return False


async def _get_connector(edc_id: str) -> dict:
    """
    Retrieves connector configuration from the database.

    Args:
        edc_id (str): MongoDB ID of the connector.

    Returns:
        dict: Connector document.

    Raises:
        HTTPException: If the connector does not exist.
    """

    db = get_db()
    connector = await db["connectors"].find_one({"_id": ObjectId(edc_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="EDC not found")
    return connector


def _parse_contract_item(item: dict, edc_id: str) -> Contract:
    """
    Parses a raw contract JSON object into a `Contract` model.

    Args:
        item (dict): Raw contract data returned by the EDC.
        edc_id (str): ID of the connector associated with the contract.

    Returns:
        Contract: Parsed contract model.
    """

    assets = []
    assets_selector = item.get("assetsSelector")

    if isinstance(assets_selector, dict):
        assets.append(assets_selector.get("operandRight"))
    elif isinstance(assets_selector, list):
        assets = [criterion.get("operandRight") for criterion in assets_selector]

    return Contract(
        edc=edc_id,
        contract_id=item.get("@id"),
        accessPolicyId=item.get("accessPolicyId"),
        contractPolicyId=item.get("contractPolicyId"),
        assetsSelector=assets,
        context=item.get("@context", {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"})
    )
