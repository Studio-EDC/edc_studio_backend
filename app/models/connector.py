"""
Connector model definition.

This module defines the data models related to EDC connectors.
A connector represents an Eclipse Data Connector (EDC) instance that can
act as a provider or consumer of data assets. Each connector includes
network port configurations, endpoint URLs, authentication information,
and operational state.

The models are implemented using Pydantic for data validation, type
hinting, and JSON serialization, ensuring consistency across the
EDC Studio Backend.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID, uuid4

class PortConfig(BaseModel):
    """
    Defines the port configuration for an EDC connector instance.

    Each connector uses multiple ports for communication across
    control, protocol, and management interfaces.

    Example:
        >>> ports = PortConfig(
        ...     http=8181,
        ...     management=8182,
        ...     protocol=8183,
        ...     control=8184,
        ...     public=8185,
        ...     version=1
        ... )
    """

    http: int
    """Port used for the HTTP interface."""

    management: int
    """Port used for the management API."""

    protocol: int
    """Port used for the data transfer protocol."""

    control: int
    """Port used for control-plane communication."""

    public: int
    """Publicly accessible port of the connector."""

    version: int
    """Version number of the port configuration."""

class Endpoints(BaseModel):
    """
    Defines the accessible endpoints of an EDC connector.

    These endpoints represent the URLs exposed by the connector
    for management and data exchange operations.

    Example:
        >>> endpoints = Endpoints(
        ...     management="http://localhost:8182/api/v1/management",
        ...     protocol="http://localhost:8183/api/v1/protocol"
        ... )
    """

    management: str
    """Management API endpoint URL."""

    protocol: Optional[str] = None
    """Protocol endpoint URL (optional)."""

    public: Optional[str] = None
    """Public endpoint URL (optional)."""

class Connector(BaseModel):
    """
    Represents an Eclipse Data Connector (EDC) instance.

    A connector can operate as a **provider** or **consumer** of data,
    depending on its assigned type. It may run locally (managed mode)
    or remotely (remote mode), and exposes endpoints for communication.

    Example:
        >>> connector = Connector(
        ...     name="EDC Provider 01",
        ...     description="Primary provider connector",
        ...     type="provider",
        ...     state="running",
        ...     mode="managed",
        ...     ports=PortConfig(http=8181, management=8182, protocol=8183, control=8184, public=8185, version=1),
        ...     endpoints_url=Endpoints(
        ...         management="http://localhost:8182/api/v1/management",
        ...         protocol="http://localhost:8183/api/v1/protocol"
        ...     ),
        ...     domain="localhost"
        ... )
        >>> print(connector.name)
        EDC Provider 01
    """

    name: str
    """Human-readable name of the connector."""

    owner: Optional[str] = None

    description: Optional[str] = None
    """Optional text description of the connector."""

    type: Literal["provider", "consumer"]
    """Connector role within the EDC ecosystem (`provider` or `consumer`)."""

    ports: Optional[PortConfig] = None
    """Port configuration for this connector (optional)."""

    api_key: Optional[str] = None
    """Authentication key used to secure management API access."""

    state: Literal["running", "stopped"]
    """Operational state of the connector (`running` or `stopped`)."""

    mode: Literal["managed", "remote"]
    """Execution mode of the connector (`managed` = local, `remote` = external)."""

    endpoints_url: Optional[Endpoints] = None
    """URLs for management and protocol endpoints (optional)."""

    domain: Optional[str] = None
    """Network domain or hostname where the connector is accessible."""