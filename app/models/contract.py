"""
Contract model definition.

This module defines the `Contract` data model, which represents a
contract definition within the Eclipse Data Connector (EDC) framework.
Contracts specify the policies that govern data access and usage between
connectors, linking assets with associated policy definitions.

The model follows the EDC specification and uses Pydantic for type
validation and serialization.
"""

from pydantic import BaseModel
from typing import List, Dict


class Contract(BaseModel):
    """
    Represents a contract definition in the EDC ecosystem.

    A contract links assets with access and contract policies, defining
    the rules under which data can be exchanged between provider and
    consumer connectors. Each contract is identified by a unique
    `contract_id` and associated with a specific EDC connector.

    Example:
        >>> contract = Contract(
        ...     edc="edc-provider-01",
        ...     contract_id="contract-1234",
        ...     accessPolicyId="policy-access-001",
        ...     contractPolicyId="policy-contract-001",
        ...     assetsSelector=["asset-001", "asset-002"]
        ... )
        >>> print(contract.contract_id)
        contract-1234
    """

    edc: str
    """Identifier of the EDC connector associated with this contract."""

    contract_id: str 
    """Unique identifier of the contract definition."""

    accessPolicyId: str
    """Identifier of the access policy that regulates data access."""

    contractPolicyId: str
    """Identifier of the contract policy that defines usage conditions."""

    assetsSelector: List[str]
    """List of asset identifiers included in this contract."""

    context: Dict[str, str] = {
        "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
    }
    """JSON-LD context used for EDC vocabulary resolution."""