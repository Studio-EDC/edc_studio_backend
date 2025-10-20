"""
Transfer schemas.

This module defines the Pydantic schemas used to represent and validate
data exchange operations between EDC connectors. These schemas are used
for both API requests and responses related to catalog retrieval, contract
negotiation, transfer initiation, and status checks.

Schemas:
    - TransferResponse: Full transfer record returned by the API.
    - RequestCatalog: Structure for requesting a provider's data catalog.
    - NegotitateContract: Structure for initiating contract negotiation.
    - ContractAgreement: Structure for retrieving an established agreement.
    - StartTransfer: Structure for starting a data transfer.
    - CheckTransfer: Structure for checking transfer status.
"""

from pydantic import BaseModel
from typing import Literal, Optional


class TransferResponse(BaseModel):
    """
    Represents a complete data transfer record between two EDC connectors.

    This schema captures all metadata related to a transfer, including
    contract identifiers, transfer process information, and flow type.

    Example:
        >>> transfer = TransferResponse(
        ...     id="transfer-001",
        ...     consumer="edc-consumer-01",
        ...     provider="edc-provider-01",
        ...     asset="asset-001",
        ...     has_policy_id="policy-001",
        ...     negotiate_contract_id="neg-001",
        ...     contract_agreement_id="agreement-001",
        ...     transfer_process_id="process-001",
        ...     transfer_flow="push"
        ... )
        >>> print(transfer.transfer_flow)
        push
    """

    id: str
    """Unique identifier of the transfer record."""

    consumer: str
    """Identifier of the consumer EDC connector."""

    provider: str
    """Identifier of the provider EDC connector."""

    asset: str
    """Identifier of the asset involved in the transfer."""

    has_policy_id: str
    """Identifier of the policy governing this transfer."""

    negotiate_contract_id: str
    """Identifier of the contract negotiation process."""

    contract_agreement_id: str
    """Identifier of the established contract agreement."""

    transfer_process_id: str
    """Identifier of the transfer process in the EDC connector."""

    transfer_flow: Literal["push", "pull"]
    """Type of transfer flow: `push` or `pull`."""

    authorization: Optional[str] = None
    """Optional authorization token used for secured transfers."""
    
    endpoint: Optional[str] = None
    """Optional endpoint URL used for accessing or delivering data."""

class RequestCatalog(BaseModel):
    """
    Represents a catalog request between two connectors.

    Used to retrieve the list of assets available for negotiation
    from a provider connector.

    Example:
        >>> request = RequestCatalog(
        ...     consumer="edc-consumer-01",
        ...     provider="edc-provider-01"
        ... )
    """

    consumer: str
    """Identifier of the consumer connector requesting the catalog."""

    provider: str
    """Identifier of the provider connector offering assets."""

class NegotitateContract(BaseModel):
    """
    Represents a contract negotiation request between two connectors.

    Used to initiate a negotiation for a specific asset based on
    a given contract offer ID.

    Example:
        >>> negotiation = NegotitateContract(
        ...     consumer="edc-consumer-01",
        ...     provider="edc-provider-01",
        ...     contract_offer_id="offer-001",
        ...     asset="asset-001"
        ... )
    """

    consumer: str
    """Identifier of the consumer connector."""

    provider: str
    """Identifier of the provider connector."""

    contract_offer_id: str
    """Identifier of the offered contract to be negotiated."""

    asset: str
    """Identifier of the asset associated with this contract offer."""

class ContractAgreement(BaseModel):
    """
    Represents a request to retrieve a finalized contract agreement.

    Example:
        >>> agreement = ContractAgreement(
        ...     consumer="edc-consumer-01",
        ...     id_contract_negotiation="neg-001"
        ... )
    """

    consumer: str
    """Identifier of the consumer connector."""

    id_contract_negotiation: str
    """Identifier of the previously negotiated contract."""

class StartTransfer(BaseModel):
    """
    Represents the information required to start a transfer process.

    Example:
        >>> start = StartTransfer(
        ...     consumer="edc-consumer-01",
        ...     provider="edc-provider-01",
        ...     contract_agreement_id="agreement-001"
        ... )
    """

    consumer: str
    """Identifier of the consumer connector initiating the transfer."""

    provider: str
    """Identifier of the provider connector offering the data."""

    contract_agreement_id: str
    """Identifier of the established contract agreement."""

class CheckTransfer(BaseModel):
    """
    Represents a request to check the status of a transfer process.

    Example:
        >>> check = CheckTransfer(
        ...     consumer="edc-consumer-01",
        ...     transfer_process_id="process-001"
        ... )
    """

    consumer: str
    """Identifier of the consumer connector."""

    transfer_process_id: str
    """Identifier of the transfer process to check."""