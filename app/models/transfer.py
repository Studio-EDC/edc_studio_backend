"""
Transfer model definition.

This module defines the `Transfer` data model used to represent
data transfer processes between EDC connectors. Each transfer
links a provider and consumer connector, an asset, and the
associated contractual and policy information required to
perform the exchange.

Transfers may occur in `push` or `pull` mode, depending on which
connector initiates the data movement.
"""

from pydantic import BaseModel
from typing import List, Dict, Literal, Optional


class Transfer(BaseModel):
    """
    Represents a data transfer process between EDC connectors.

    A transfer defines the relationship between the provider and
    consumer connectors, the asset being transferred, and the
    contractual context that authorizes the exchange.

    Example:
        >>> transfer = Transfer(
        ...     consumer="edc-consumer-01",
        ...     provider="edc-provider-01",
        ...     asset="asset-001",
        ...     has_policy_id="policy-001",
        ...     negotiate_contract_id="contract-req-001",
        ...     contract_agreement_id="agreement-001",
        ...     transfer_process_id="transfer-123",
        ...     transfer_flow="push",
        ...     authorization="Bearer <token>",
        ...     endpoint="http://localhost:8282/api/v1/data"
        ... )
        >>> print(transfer.transfer_flow)
        push
    """

    consumer: str
    """Identifier of the consumer EDC connector involved in the transfer."""

    provider: str
    """Identifier of the provider EDC connector supplying the asset."""

    asset: str
    """Identifier of the asset being transferred."""

    has_policy_id: str
    """Identifier of the policy that governs this transfer."""

    negotiate_contract_id: str
    """Identifier of the negotiation process that led to this transfer."""

    contract_agreement_id: str
    """Identifier of the finalized contract agreement for the transfer."""

    transfer_process_id: str
    """Unique identifier of the transfer process in EDC."""

    transfer_flow: Literal["push", "pull"]
    """Direction of the data flow:
    - `push`: the provider sends the data.
    - `pull`: the consumer retrieves the data.
    """

    authorization: Optional[str] = None
    """Optional authorization token used for secure data access."""

    endpoint: Optional[str] = None
    """Optional endpoint URL used for data delivery or retrieval."""