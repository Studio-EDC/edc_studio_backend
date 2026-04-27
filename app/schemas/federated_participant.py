"""
Schemas for federated participant responses.
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

from app.models.federated_participant import ManualChecklist


FederatedParticipantStatus = Literal[
    "DRAFT",
    "DID_READY",
    "REGISTERED_IN_EDC_MANAGER",
    "CREDENTIALS_INSTALLED",
    "READY",
]


class FederatedParticipantResponse(BaseModel):
    """Federated participant returned by the API."""

    id: str
    participant_did: str
    legal_name: str
    lrn_value: str
    headquarter_address_country_code: str
    legal_address_country_code: str
    connector_id: str
    connector_name: Optional[str] = None
    public_domain: str
    protocol_endpoint: Optional[str] = None
    notes: Optional[str] = None
    checklist: ManualChecklist
    status: FederatedParticipantStatus
    created_at: datetime
    updated_at: datetime


class DidDocumentResponse(BaseModel):
    """Generated DID document and publication URL."""

    did_document_url: str
    did_document: dict


class ManualRegistrationResponse(BaseModel):
    """Payload and curl command for manual registration in edc-manager."""

    payload: dict
    curl_command: str


class DidValidationResponse(BaseModel):
    """Result of validating a did:web document and its protocol endpoint."""

    did_document_url: str
    did_document_reachable: bool
    did_document_status_code: Optional[int] = None
    did_document_id_matches: bool = False
    protocol_service_found: bool = False
    protocol_service_matches_expected: bool = False
    protocol_endpoint_reachable: bool = False
    protocol_endpoint_status_code: Optional[int] = None
    resolved_protocol_endpoint: Optional[str] = None
    expected_protocol_endpoint: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
