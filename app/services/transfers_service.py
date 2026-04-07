"""
Transfers Service.

This module handles the complete data exchange lifecycle between EDC
connectors, including catalog retrieval, contract negotiation,
agreement validation, and data transfer initiation (PUSH or PULL).

It acts as the orchestration layer for data transactions in the EDC Studio
Backend, communicating with the connectors' Management and Protocol APIs.

Main responsibilities:
    - Requesting and parsing asset catalogs between connectors.
    - Negotiating and validating contract agreements.
    - Starting, monitoring, and managing data transfers.
    - Managing local transfer metadata and HTTP logger containers.

All operations follow the EDC protocol specifications and use the
dataspace-protocol-http communication channel.
"""

import os
from dotenv import load_dotenv
from fastapi import HTTPException
import httpx
from app.db.client import get_db
from bson import ObjectId
import subprocess
from pathlib import Path

from app.models.transfer import Transfer
from app.util.edc_helpers import get_base_url


def _get_management_url(connector: dict, suffix: str) -> str:
    """
    Build the management API URL for a connector.

    Args:
        connector (dict): Connector configuration document.
        suffix (str): Management API suffix, e.g. '/v3/catalog/request'.

    Returns:
        str: Full management URL.

    Raises:
        ValueError: If connector mode is invalid or endpoints are missing.
    """
    if connector["mode"] == "managed":
        return get_base_url(connector, suffix)
    elif connector["mode"] == "remote":
        endpoints = connector.get("endpoints_url") or {}
        management = endpoints.get("management")
        if not management:
            raise ValueError("Remote connector management endpoint not configured")
        return f"{management.rstrip('/')}{suffix}"
    else:
        raise ValueError("Invalid connector mode")


def _get_protocol_url(connector: dict) -> str:
    """
    Build the protocol API URL for a connector.

    Args:
        connector (dict): Connector configuration document.

    Returns:
        str: Full protocol URL.

    Raises:
        ValueError: If connector mode is invalid or endpoints are missing.
    """
    if connector["mode"] == "managed":
        protocol_port = connector["ports"]["protocol"]
        connector_type = connector.get("type", "provider")
        return f"http://edc-{connector_type}-{connector['_id']}:{protocol_port}/protocol"
    elif connector["mode"] == "remote":
        endpoints = connector.get("endpoints_url") or {}
        protocol = endpoints.get("protocol")
        if not protocol:
            raise ValueError("Remote connector protocol endpoint not configured")
        return protocol
    else:
        raise ValueError("Invalid connector mode")


def _get_participant_id(connector: dict) -> str:
    """
    Return the participant id to use in DSP messages.

    If a connector-specific participant id is not stored in Mongo, fall back
    to the connector type, which matches the current deployment ('consumer'/'provider').

    Args:
        connector (dict): Connector configuration document.

    Returns:
        str: Participant identifier.
    """
    return (
        connector.get("participant_id")
        or connector.get("participantId")
        or connector.get("dspace_participant_id")
        or connector.get("type")
        or "provider"
    )


def _find_catalog_offer(catalog: dict, asset_id: str) -> dict:
    """
    Find the odrl:hasPolicy offer for a given asset in a catalog response.

    Args:
        catalog (dict): Catalog JSON returned by EDC.
        asset_id (str): Asset identifier to search.

    Returns:
        dict: odrl:hasPolicy object for the asset, or {} if not found.
    """
    datasets = (catalog or {}).get("dcat:dataset") or []
    if isinstance(datasets, dict):
        datasets = [datasets]

    for dataset in datasets:
        if not isinstance(dataset, dict):
            continue

        dataset_id = (dataset.get("@id") or dataset.get("id") or "").strip()
        if dataset_id != asset_id:
            continue

        offer = dataset.get("odrl:hasPolicy") or {}
        if isinstance(offer, dict):
            return offer

    return {}


def _normalize_catalog_permission(permission_value):
    """
    Convert catalog ODRL permissions into the shape expected by
    /v3/contractnegotiations on the EDC management API.

    Example conversion:
        odrl:permission -> permission
        odrl:action.@id=odrl:use -> action=use
        odrl:constraint.odrl:leftOperand.@id=edc:MembershipCredential
            -> leftOperand=MembershipCredential
        odrl:operator.@id=odrl:eq -> operator=eq
    """
    if permission_value in (None, "", {}):
        return []

    permissions = permission_value if isinstance(permission_value, list) else [permission_value]
    result = []

    for perm in permissions:
        if not isinstance(perm, dict):
            continue

        action_raw = perm.get("odrl:action")
        action = None
        if isinstance(action_raw, dict):
            action = action_raw.get("@id", "")
            if isinstance(action, str) and ":" in action:
                action = action.split(":")[-1]
        elif isinstance(action_raw, str):
            action = action_raw.split(":")[-1]

        constraint_raw = perm.get("odrl:constraint")
        constraint = None
        if isinstance(constraint_raw, dict):
            left = constraint_raw.get("odrl:leftOperand")
            if isinstance(left, dict):
                left = left.get("@id", "")
                if isinstance(left, str) and ":" in left:
                    left = left.split(":")[-1]
            elif isinstance(left, str) and ":" in left:
                left = left.split(":")[-1]

            operator = constraint_raw.get("odrl:operator")
            if isinstance(operator, dict):
                operator = operator.get("@id", "")
                if isinstance(operator, str) and ":" in operator:
                    operator = operator.split(":")[-1]
            elif isinstance(operator, str) and ":" in operator:
                operator = operator.split(":")[-1]

            right = constraint_raw.get("odrl:rightOperand")

            constraint = {
                "leftOperand": left,
                "operator": operator,
                "rightOperand": right,
            }

        item = {
            "action": action or "use",
        }
        if constraint:
            item["constraint"] = constraint

        result.append(item)

    return result


def _normalize_catalog_rule_collection(value):
    """
    Normalize prohibition/obligation collections coming from the catalog.

    For now we keep their structure as-is, just ensuring they are lists.
    """
    if value in (None, "", {}):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


def _build_policy_from_catalog_offer(
    offer: dict,
    asset_id: str,
    provider_participant_id: str,
    consumer_participant_id: str,
) -> dict:
    """
    Convert the catalog offer into the negotiation policy payload expected by
    the EDC management API.

    The key point is to reuse the *meaning* of the same offer returned by the
    catalog, but reshape it into the format accepted by the management API.

    Args:
        offer (dict): odrl:hasPolicy object from the catalog.
        asset_id (str): Asset identifier.
        provider_participant_id (str): Provider participant id.
        consumer_participant_id (str): Consumer participant id.

    Returns:
        dict: Policy object suitable for ContractRequest.

    Raises:
        HTTPException: If the offer has no @id.
    """
    offer_id = offer.get("@id")
    if not offer_id:
        raise HTTPException(status_code=404, detail="Catalog offer has no @id")

    return {
        "@type": "Offer",
        "@id": offer_id,
        "assigner": provider_participant_id,
        "assignee": consumer_participant_id,
        "permission": _normalize_catalog_permission(offer.get("odrl:permission")),
        "prohibition": _normalize_catalog_rule_collection(offer.get("odrl:prohibition")),
        "obligation": _normalize_catalog_rule_collection(offer.get("odrl:obligation")),
        "target": asset_id,
    }


async def catalog_request_service(consumer_id: str, provider_id: str) -> dict:
    """
    Requests the asset catalog from a provider connector through an EDC consumer.

    Args:
        consumer_id (str): MongoDB ID of the consumer connector.
        provider_id (str): MongoDB ID of the provider connector.

    Raises:
        ValueError: If either connector is not found.

    Returns:
        dict: Catalog response from the provider connector.
    """

    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})
    provider = await db["connectors"].find_one({"_id": ObjectId(provider_id)})

    if not consumer or not provider:
        raise ValueError("Consumer or provider connector not found")

    return await catalog_request_curl(consumer, provider)


async def catalog_request_curl(consumer: dict, provider: dict):
    """
    Sends an HTTP request to retrieve the catalog of available assets from a provider.

    Depending on the consumer’s mode (managed or remote), it builds the proper
    management and protocol URLs.

    Args:
        consumer (dict): Consumer connector document.
        provider (dict): Provider connector document.

    Raises:
        HTTPException: If API key is missing or EDC communication fails.

    Returns:
        dict: JSON response containing the provider's catalog.
    """

    management_url = _get_management_url(consumer, "/v3/catalog/request")
    protocol_url = _get_protocol_url(provider)

    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "counterPartyAddress": protocol_url,
        "protocol": "dataspace-protocol-http"
    }

    api_key = consumer["api_key"]
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")

    headers = {
        "x-api-key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(management_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"EDC error: {exc.response.text}"
            )


async def negotiate_contract_service(consumer_id: str, provider_id: str, contract_offer_id: str, asset: str) -> dict:
    """
    Starts a contract negotiation between a consumer and provider connector.

    Args:
        consumer_id (str): Consumer connector ID.
        provider_id (str): Provider connector ID.
        contract_offer_id (str): Contract offer identifier.
        asset (str): Asset identifier.

    Raises:
        ValueError: If connectors are not found.

    Returns:
        dict: EDC negotiation response.
    """

    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})
    provider = await db["connectors"].find_one({"_id": ObjectId(provider_id)})

    if not consumer or not provider:
        raise ValueError("Consumer or provider connector not found")

    return await negotiate_contract_curl(consumer, provider, contract_offer_id, asset)


async def negotiate_contract_curl(consumer: dict, provider: dict, contract_offer_id: str, asset: str):
    """
    Performs an HTTP request to the EDC Management API to initiate contract negotiation.

    This implementation first requests the catalog through the consumer, locates
    the real current offer for the requested asset, and builds the negotiation
    policy from that offer. The provided contract_offer_id is treated as optional
    and informative only, because catalog offer ids may rotate between calls.
    """

    management_url = _get_management_url(consumer, "/v3/contractnegotiations")
    protocol_url = _get_protocol_url(provider)

    provider_participant_id = _get_participant_id(provider)
    consumer_participant_id = _get_participant_id(consumer)

    # 1. Request the current provider catalog through the consumer
    catalog = await catalog_request_curl(consumer, provider)

    # 2. Locate the current real catalog offer for the requested asset
    catalog_offer = _find_catalog_offer(catalog, asset)
    if not catalog_offer:
        raise HTTPException(
            status_code=404,
            detail=f"Catalog offer not found for asset '{asset}'"
        )

    real_offer_id = catalog_offer.get("@id")
    if not real_offer_id:
        raise HTTPException(
            status_code=404,
            detail=f"Catalog offer for asset '{asset}' has no @id"
        )

    # Catalog ids may rotate, so always negotiate with the current catalog value.
    effective_offer_id = real_offer_id

    # 3. Build a management-API-compatible policy from the catalog offer
    policy = _build_policy_from_catalog_offer(
        offer=catalog_offer,
        asset_id=asset,
        provider_participant_id=provider_participant_id,
        consumer_participant_id=consumer_participant_id,
    )
    policy["@id"] = effective_offer_id

    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@type": "ContractRequest",
        "counterPartyAddress": protocol_url,
        "counterPartyId": provider_participant_id,
        "protocol": "dataspace-protocol-http",
        "policy": policy,
        "callbackAddresses": []
    }

    api_key = consumer["api_key"]
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")

    headers = {
        "x-api-key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(management_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"EDC error: {exc.response.text}"
            )


async def get_contract_agreement_service(consumer_id: str, id_contract_negotiation: str) -> dict:
    """
    Retrieves a contract agreement based on a negotiation ID.

    Args:
        consumer_id (str): Consumer connector ID.
        id_contract_negotiation (str): Contract negotiation ID.

    Returns:
        dict: Agreement details from EDC.
    """

    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})

    if not consumer:
        raise ValueError("Consumer or provider connector not found")

    return await get_contract_agreement_curl(consumer, id_contract_negotiation)


async def get_contract_agreement_curl(consumer: dict, id_contract_negotiation: str):
    """
    Performs a GET request to the EDC API to retrieve contract agreement details.

    Args:
        consumer (dict): Consumer connector data.
        id_contract_negotiation (str): Contract negotiation ID.

    Returns:
        dict: Agreement data from EDC.
    """

    management_url = _get_management_url(consumer, f"/v3/contractnegotiations/{id_contract_negotiation}")

    api_key = consumer["api_key"]
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")

    headers = {
        "x-api-key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(management_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"EDC error: {exc.response.text}"
            )


def start_http_server_service():
    """
    Starts or restarts the HTTP logger Docker container used to receive
    data transfer callbacks.

    The container is built from `util/http-request-logger` and automatically
    joins the configured EDC Docker network.
    """

    project_root = Path(__file__).resolve().parent.parent
    dockerfile_path = project_root / "util" / "http-request-logger"

    try:
        result = subprocess.check_output(["docker", "ps", "--filter", "name=http-logger", "--filter", "status=running", "-q"])
        if result.strip():
            print("El contenedor 'http-logger' ya está corriendo.")
            return
    except subprocess.CalledProcessError:
        pass

    try:
        result = subprocess.check_output(["docker", "ps", "-a", "--filter", "name=http-logger", "--filter", "status=exited", "-q"])
        if result.strip():
            subprocess.run(["docker", "start", "http-logger"], check=True)
            print("Contenedor 'http-logger' iniciado.")
            return
    except subprocess.CalledProcessError:
        pass

    subprocess.run(["docker", "build", "-t", "http-request-logger", str(dockerfile_path)], check=True)
    load_dotenv()
    network_name = os.getenv("NETWORK_NAME", "edc-network")
    subprocess.run([
        "docker", "run", "-d", "--name", "http-logger", "--network", network_name, "-p", "4000:4000", "http-request-logger"
    ], check=True)
    print("Contenedor 'http-logger' creado y ejecutado.")


def stop_http_server_service():
    """
    Stops and removes the HTTP logger Docker container if running.
    """

    subprocess.run(["docker", "rm", "-f", "http-logger"], check=True)


async def start_transfer_service(consumer_id: str, provider_id: str, contract_agreement_id: str) -> dict:
    """
    Initiates a PUSH data transfer from provider to consumer.

    Args:
        consumer_id (str): Consumer connector ID.
        provider_id (str): Provider connector ID.
        contract_agreement_id (str): Agreement ID that authorizes transfer.

    Returns:
        dict: JSON response from EDC transfer API.
    """

    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})
    provider = await db["connectors"].find_one({"_id": ObjectId(provider_id)})

    if not consumer or not provider:
        raise ValueError("Consumer or provider connector not found")

    return await start_transfer_curl(consumer, provider, contract_agreement_id)


async def start_transfer_curl(consumer: dict, provider: dict, contract_agreement_id: str):
    """
    Executes the HTTP POST to the EDC API to start a PUSH transfer process.

    Args:
        consumer (dict): Consumer connector data.
        provider (dict): Provider connector data.
        contract_agreement_id (str): Contract agreement ID.

    Returns:
        dict: Transfer initiation response.
    """

    management_url = _get_management_url(consumer, "/v3/transferprocesses")
    protocol_url = _get_protocol_url(provider)
    provider_participant_id = _get_participant_id(provider)

    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@type": "TransferRequestDto",
        "connectorId": provider_participant_id,
        "counterPartyId": provider_participant_id,
        "counterPartyAddress": protocol_url,
        "contractId": contract_agreement_id,
        "protocol": "dataspace-protocol-http",
        "transferType": "HttpData-PUSH",
        "dataDestination": {
            "type": "HttpData",
            "baseUrl": "http://http-logger:4000/api/consumer/store"
        }
    }

    api_key = consumer["api_key"]
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")

    headers = {
        "x-api-key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(management_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"EDC error: {exc.response.text}"
            )


async def check_transfer_service(consumer_id: str, transfer_process_id: str) -> dict:
    """
    Retrieves the current status of a transfer process from the consumer connector.

    Args:
        consumer_id (str): MongoDB ID of the consumer connector.
        transfer_process_id (str): Identifier of the transfer process in EDC.

    Raises:
        ValueError: If the consumer connector is not found.

    Returns:
        dict: Transfer process details including current state and type.
    """

    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})

    if not consumer:
        raise ValueError("Consumer or provider connector not found")

    return await check_transfer_curl(consumer, transfer_process_id)


async def check_transfer_curl(consumer: dict, transfer_process_id: str):
    """
    Sends an HTTP GET request to the EDC Management API to obtain the
    state of a given transfer process.

    Args:
        consumer (dict): Consumer connector configuration document.
        transfer_process_id (str): Transfer process identifier.

    Raises:
        HTTPException: If EDC communication fails.

    Returns:
        dict: JSON response describing the current transfer state.
    """

    management_url = _get_management_url(consumer, f"/v3/transferprocesses/{transfer_process_id}")

    api_key = consumer["api_key"]
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")

    headers = {
        "x-api-key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(management_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"EDC error: {exc.response.text}"
            )


async def create_transfer_service(data: Transfer) -> str:
    """
    Registers a new transfer in the local MongoDB collection.

    Args:
        data (Transfer): Transfer object containing consumer, provider,
                         and metadata details.

    Raises:
        HTTPException: If consumer or provider connector is not found.

    Returns:
        str: MongoDB ID of the created transfer document.
    """

    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(data.consumer)})
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")

    provider = await db["connectors"].find_one({"_id": ObjectId(data.provider)})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    transfer_dict = data.model_dump(by_alias=True)
    transfer_dict["consumer"] = consumer["_id"]
    transfer_dict["provider"] = provider["_id"]

    result = await db["transfers"].insert_one(transfer_dict)
    return str(result.inserted_id)


async def get_all_transfers_service():
    """
    Retrieves all transfers stored in the local database.

    This function also populates each transfer with its corresponding
    consumer, provider, and asset documents, replacing ObjectIds with
    full document data.

    Returns:
        list[dict]: List of all transfer documents with populated fields.
    """

    db = get_db()
    transfers_cursor = db["transfers"].find()
    transfers = []

    async for transfer in transfers_cursor:
        transfer["id"] = str(transfer["_id"])
        del transfer["_id"]

        if "consumer" in transfer and isinstance(transfer["consumer"], ObjectId):
            consumer = await db["connectors"].find_one({"_id": transfer["consumer"]})
            transfer["consumer"] = convert_objectids(consumer) if consumer else None

        if "provider" in transfer and isinstance(transfer["provider"], ObjectId):
            provider = await db["connectors"].find_one({"_id": transfer["provider"]})
            transfer["provider"] = convert_objectids(provider) if provider else None

        if "asset" in transfer and isinstance(transfer["asset"], ObjectId):
            asset = await db["assets"].find_one({"_id": transfer["asset"]})
            transfer["asset"] = convert_objectids(asset) if asset else None

        transfers.append(transfer)

    return transfers


def convert_objectids(doc: dict) -> dict:
    """
    Converts MongoDB ObjectId fields into string identifiers.

    Args:
        doc (dict): MongoDB document with potential ObjectId values.

    Returns:
        dict: Document with ObjectIds replaced by their string representation.
    """

    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        else:
            result[k] = v
    if "_id" in doc:
        result["id"] = str(doc["_id"])
    return result


async def start_transfer_service_pull(consumer_id: str, provider_id: str, contract_agreement_id: str) -> dict:
    """
    Initiates a PULL data transfer from provider to consumer.

    Args:
        consumer_id (str): Consumer connector ID.
        provider_id (str): Provider connector ID.
        contract_agreement_id (str): Agreement authorizing data transfer.

    Raises:
        ValueError: If connectors are not found.

    Returns:
        dict: Transfer process response from the EDC Management API.
    """

    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})
    provider = await db["connectors"].find_one({"_id": ObjectId(provider_id)})

    if not consumer or not provider:
        raise ValueError("Consumer or provider connector not found")

    return await start_transfer_curl_pull(consumer, provider, contract_agreement_id)


async def start_transfer_curl_pull(consumer: dict, provider: dict, contract_agreement_id: str):
    """
    Executes a PULL data transfer request via the EDC Management API.

    Args:
        consumer (dict): Consumer connector configuration.
        provider (dict): Provider connector configuration.
        contract_agreement_id (str): Valid contract agreement ID.

    Returns:
        dict: JSON response from the EDC API confirming transfer initiation.
    """

    management_url = _get_management_url(consumer, "/v3/transferprocesses")
    protocol_url = _get_protocol_url(provider)
    provider_participant_id = _get_participant_id(provider)

    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@type": "TransferRequestDto",
        "connectorId": provider_participant_id,
        "counterPartyId": provider_participant_id,
        "counterPartyAddress": protocol_url,
        "contractId": contract_agreement_id,
        "protocol": "dataspace-protocol-http",
        "transferType": "HttpData-PULL"
    }

    api_key = consumer["api_key"]
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")

    headers = {
        "x-api-key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(management_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"EDC error: {exc.response.text}"
            )


async def check_transfer_data_pull_service(consumer_id: str, transfer_process_id: str) -> dict:
    """
    Retrieves the endpoint (data address) of a PULL transfer once created.

    Args:
        consumer_id (str): Consumer connector ID.
        transfer_process_id (str): EDC transfer process ID.

    Raises:
        ValueError: If the consumer connector is not found.

    Returns:
        dict: Data address response from the EDC Management API.
    """

    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})

    if not consumer:
        raise ValueError("Consumer or provider connector not found")

    return await check_transfer_data_curl_pull(consumer, transfer_process_id)


async def check_transfer_data_curl_pull(consumer: dict, transfer_process_id: str):
    """
    Sends a GET request to fetch the data address (EDR) for a PULL transfer.

    Args:
        consumer (dict): Consumer connector configuration.
        transfer_process_id (str): Transfer process ID.

    Returns:
        dict: JSON data address from EDC if available.
    """

    management_url = _get_management_url(consumer, f"/v3/edrs/{transfer_process_id}/dataaddress")

    api_key = consumer["api_key"]
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")

    headers = {
        "x-api-key": api_key
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(management_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"EDC error: {exc.response.text}"
            )