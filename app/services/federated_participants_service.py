"""
Business logic for federated participants.
"""

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote

import httpx
from bson import ObjectId
from fastapi import HTTPException

from app.db.client import get_db
from app.models.federated_participant import FederatedParticipant
from app.schemas.federated_participant import (
    DidValidationResponse,
    FederatedParticipantResponse,
    FederatedParticipantStatus,
    ManualRegistrationResponse,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_connector_running(connector: Optional[dict]) -> bool:
    return bool(connector and connector.get("state") == "running")


def _is_did_automatically_published(
    participant: dict, connector: Optional[dict]
) -> bool:
    if not _is_connector_running(connector):
        return False

    try:
        _did_to_document_url(participant["participant_did"])
    except HTTPException:
        return False

    return True


def _compute_status(
    participant: dict, connector: Optional[dict]
) -> FederatedParticipantStatus:
    checklist = participant.get("checklist", {})
    did_published = _is_did_automatically_published(participant, connector)
    registered = checklist.get("registered_in_edc_manager", False)
    credentials_installed = checklist.get("credentials_installed", False)

    if did_published and registered and credentials_installed:
        return "READY"
    if credentials_installed:
        return "CREDENTIALS_INSTALLED"
    if registered:
        return "REGISTERED_IN_EDC_MANAGER"
    if did_published:
        return "DID_READY"
    return "DRAFT"


def _normalize_domain(domain: str) -> str:
    normalized = domain.strip()
    if normalized.startswith("https://"):
        normalized = normalized[len("https://"):]
    elif normalized.startswith("http://"):
        normalized = normalized[len("http://"):]
    return normalized.strip("/ ")


def _resolve_protocol_endpoint(participant: dict, connector: Optional[dict]) -> Optional[str]:
    explicit = participant.get("protocol_endpoint")
    if explicit:
        return explicit

    if connector:
        endpoints = connector.get("endpoints_url") or {}
        if endpoints.get("protocol"):
            return endpoints["protocol"]
        if connector.get("domain"):
            return f"https://{_normalize_domain(connector['domain'])}/protocol"

    domain = participant.get("public_domain")
    if domain:
        return f"https://{_normalize_domain(domain)}/protocol"

    return None


def _did_to_document_url(participant_did: str) -> str:
    if not participant_did.startswith("did:web:"):
        raise HTTPException(status_code=400, detail="Only did:web identifiers are supported")

    identifier = participant_did[len("did:web:"):]
    segments = [unquote(segment) for segment in identifier.split(":") if segment]
    if not segments:
        raise HTTPException(status_code=400, detail="Invalid did:web identifier")

    host = segments[0]
    path_segments = segments[1:]

    if path_segments:
        return f"https://{host}/{'/'.join(path_segments)}/did.json"
    return f"https://{host}/.well-known/did.json"


def _build_did_document(participant: dict, connector: Optional[dict]) -> dict:
    protocol_endpoint = _resolve_protocol_endpoint(participant, connector)
    if not protocol_endpoint:
        raise HTTPException(status_code=400, detail="Protocol endpoint could not be resolved")

    participant_did = participant["participant_did"]
    return {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": participant_did,
        "service": [
            {
                "id": f"{participant_did}#edc-dsp",
                "type": "ProtocolEndpoint",
                "serviceEndpoint": protocol_endpoint,
            }
        ],
    }


def _build_registration_payload(participant: dict) -> dict:
    return {
        "participantDID": participant["participant_did"],
        "lrnValue": participant["lrn_value"],
        "legalName": participant["legal_name"],
        "headQuarterAddressCountryCode": participant["headquarter_address_country_code"],
        "legalAddressCountryCode": participant["legal_address_country_code"],
    }


def _build_registration_curl(payload: dict) -> str:
    return (
        "curl -X POST \"<EDC_MANAGER_URL>/add_remote_participant\" \\\n"
        "  -H \"x-api-key: <API_KEY>\" \\\n"
        "  -H \"Content-Type: application/json\" \\\n"
        "  -d '"
        + "{\n"
        + f"    \"participantDID\": \"{payload['participantDID']}\",\n"
        + f"    \"lrnValue\": \"{payload['lrnValue']}\",\n"
        + f"    \"legalName\": \"{payload['legalName']}\",\n"
        + f"    \"headQuarterAddressCountryCode\": \"{payload['headQuarterAddressCountryCode']}\",\n"
        + f"    \"legalAddressCountryCode\": \"{payload['legalAddressCountryCode']}\"\n"
        + "  }'"
    )


async def _get_owned_connector(connector_id: str, owner_id: str) -> Optional[dict]:
    db = get_db()
    if not ObjectId.is_valid(connector_id):
        return None

    return await db["connectors"].find_one(
        {"_id": ObjectId(connector_id), "owner": owner_id}
    )


async def _get_connector(connector_id: str) -> Optional[dict]:
    db = get_db()
    if not ObjectId.is_valid(connector_id):
        return None

    return await db["connectors"].find_one({"_id": ObjectId(connector_id)})


async def _get_owned_participant(participant_id: str, owner_id: str) -> dict:
    db = get_db()
    if not ObjectId.is_valid(participant_id):
        raise HTTPException(status_code=404, detail="Federated participant not found")

    participant = await db["federated_participants"].find_one(
        {"_id": ObjectId(participant_id), "owner": owner_id}
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Federated participant not found")
    return participant


async def _serialize_participant(participant: dict) -> FederatedParticipantResponse:
    connector = await _get_owned_connector(participant["connector_id"], participant["owner"])
    checklist_data = participant.get("checklist", {}).copy()
    checklist_data["did_published"] = _is_did_automatically_published(
        participant, connector
    )
    return FederatedParticipantResponse(
        id=str(participant["_id"]),
        participant_did=participant["participant_did"],
        legal_name=participant["legal_name"],
        lrn_value=participant["lrn_value"],
        headquarter_address_country_code=participant["headquarter_address_country_code"],
        legal_address_country_code=participant["legal_address_country_code"],
        connector_id=participant["connector_id"],
        connector_name=connector["name"] if connector else None,
        public_domain=participant["public_domain"],
        protocol_endpoint=_resolve_protocol_endpoint(participant, connector),
        notes=participant.get("notes"),
        checklist=checklist_data,
        status=_compute_status(participant, connector),
        created_at=participant["created_at"],
        updated_at=participant["updated_at"],
    )


async def create_federated_participant(
    participant: FederatedParticipant, current_user: dict
) -> str:
    db = get_db()
    owner_id = str(current_user["_id"])
    connector = await _get_owned_connector(participant.connector_id, owner_id)
    if not connector:
        raise HTTPException(status_code=400, detail="Connector not found for the current user")

    document = participant.model_dump()
    now = _utcnow()
    document["owner"] = owner_id
    document["created_at"] = now
    document["updated_at"] = now

    result = await db["federated_participants"].insert_one(document)
    return str(result.inserted_id)


async def list_federated_participants(current_user: dict) -> list[FederatedParticipantResponse]:
    db = get_db()
    owner_id = str(current_user["_id"])
    participants = await db["federated_participants"].find(
        {"owner": owner_id}
    ).sort("created_at", -1).to_list(length=None)

    serialized = []
    for participant in participants:
        serialized.append(await _serialize_participant(participant))
    return serialized


async def get_federated_participant(
    participant_id: str, current_user: dict
) -> FederatedParticipantResponse:
    participant = await _get_owned_participant(participant_id, str(current_user["_id"]))
    return await _serialize_participant(participant)


async def update_federated_participant(
    participant_id: str, payload: FederatedParticipant, current_user: dict
) -> None:
    db = get_db()
    owner_id = str(current_user["_id"])
    if not ObjectId.is_valid(participant_id):
        raise HTTPException(status_code=404, detail="Federated participant not found")

    connector = await _get_owned_connector(payload.connector_id, owner_id)
    if not connector:
        raise HTTPException(status_code=400, detail="Connector not found for the current user")

    update_data = payload.model_dump()
    update_data["owner"] = owner_id
    update_data["updated_at"] = _utcnow()

    result = await db["federated_participants"].update_one(
        {"_id": ObjectId(participant_id), "owner": owner_id},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Federated participant not found")


async def delete_federated_participant(participant_id: str, current_user: dict) -> None:
    db = get_db()
    if not ObjectId.is_valid(participant_id):
        raise HTTPException(status_code=404, detail="Federated participant not found")

    result = await db["federated_participants"].delete_one(
        {"_id": ObjectId(participant_id), "owner": str(current_user["_id"])}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Federated participant not found")


async def generate_did_document(participant_id: str, current_user: dict) -> dict:
    participant = await _get_owned_participant(participant_id, str(current_user["_id"]))
    connector = await _get_owned_connector(participant["connector_id"], participant["owner"])
    did_document = _build_did_document(participant, connector)
    return {
        "did_document_url": _did_to_document_url(participant["participant_did"]),
        "did_document": did_document,
    }


async def generate_manual_registration(
    participant_id: str, current_user: dict
) -> ManualRegistrationResponse:
    participant = await _get_owned_participant(participant_id, str(current_user["_id"]))
    payload = _build_registration_payload(participant)
    return ManualRegistrationResponse(
        payload=payload,
        curl_command=_build_registration_curl(payload),
    )


async def validate_did_web(
    participant_id: str, current_user: dict
) -> DidValidationResponse:
    participant = await _get_owned_participant(participant_id, str(current_user["_id"]))
    connector = await _get_owned_connector(participant["connector_id"], participant["owner"])

    expected_protocol = _resolve_protocol_endpoint(participant, connector)
    did_document_url = _did_to_document_url(participant["participant_did"])
    errors: list[str] = []
    result = DidValidationResponse(
        did_document_url=did_document_url,
        did_document_reachable=False,
        expected_protocol_endpoint=expected_protocol,
        errors=errors,
    )

    timeout = httpx.Timeout(10.0, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            did_response = await client.get(did_document_url)
            result.did_document_status_code = did_response.status_code
            result.did_document_reachable = did_response.status_code == 200
            if did_response.status_code != 200:
                errors.append(f"did.json returned HTTP {did_response.status_code}")
                return result

            did_document = did_response.json()
            result.did_document_id_matches = (
                did_document.get("id") == participant["participant_did"]
            )
            if not result.did_document_id_matches:
                errors.append("The DID document id does not match participant_did")

            service_items = did_document.get("service") or []
            protocol_service = next(
                (
                    item
                    for item in service_items
                    if item.get("type") == "ProtocolEndpoint"
                ),
                None,
            )

            if not protocol_service:
                errors.append("No ProtocolEndpoint service was found in did.json")
                return result

            result.protocol_service_found = True
            result.resolved_protocol_endpoint = protocol_service.get("serviceEndpoint")
            result.protocol_service_matches_expected = (
                expected_protocol is not None
                and result.resolved_protocol_endpoint == expected_protocol
            )
            if expected_protocol and not result.protocol_service_matches_expected:
                errors.append("ProtocolEndpoint does not match the expected connector endpoint")

            protocol_target = result.resolved_protocol_endpoint or expected_protocol
            if not protocol_target:
                errors.append("No protocol endpoint could be resolved for validation")
                return result

            protocol_response = await client.get(protocol_target)
            result.protocol_endpoint_status_code = protocol_response.status_code
            result.protocol_endpoint_reachable = protocol_response.status_code != 404
            if not result.protocol_endpoint_reachable:
                errors.append("Protocol endpoint returned HTTP 404")

    except httpx.HTTPError as exc:
        errors.append(str(exc))

    return result


def _normalize_request_host(host: str) -> str:
    return host.split(":", 1)[0].strip().lower()


def _build_did_from_request(host: str, path_segments: list[str]) -> str:
    normalized_host = _normalize_request_host(host)
    if not normalized_host:
        raise HTTPException(status_code=400, detail="Request host is missing")

    segments = [normalized_host, *[segment for segment in path_segments if segment]]
    return "did:web:" + ":".join(segments)


async def resolve_public_did_document(host: str, path_segments: list[str]) -> dict:
    db = get_db()
    participant_did = _build_did_from_request(host, path_segments)
    participant = await db["federated_participants"].find_one(
        {"participant_did": participant_did}
    )
    if not participant:
        raise HTTPException(status_code=404, detail="DID document not found")

    connector = await _get_connector(participant["connector_id"])
    if not _is_connector_running(connector):
        raise HTTPException(
            status_code=404,
            detail="DID document is only available while the connector is running",
        )

    return _build_did_document(participant, connector)
