"""
Federated participant models.

This module defines the payload used to store a federated participant profile
inside EDC Studio. These profiles are later used to generate a DID document,
prepare the manual registration payload for edc-manager, and track the manual
operational checklist.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ManualChecklist(BaseModel):
    """Manual operational steps tracked by EDC Studio."""

    did_published: bool = False
    registered_in_edc_manager: bool = False
    credentials_installed: bool = False


class FederatedParticipant(BaseModel):
    """Federated participant profile stored by EDC Studio."""

    owner: Optional[str] = None
    participant_did: str = Field(..., min_length=3)
    legal_name: str = Field(..., min_length=1)
    lrn_value: str = Field(..., min_length=1)
    headquarter_address_country_code: str = Field(..., min_length=1)
    legal_address_country_code: str = Field(..., min_length=1)
    connector_id: str = Field(..., min_length=1)
    public_domain: str = Field(..., min_length=1)
    protocol_endpoint: Optional[str] = None
    notes: Optional[str] = None
    checklist: ManualChecklist = Field(default_factory=ManualChecklist)
