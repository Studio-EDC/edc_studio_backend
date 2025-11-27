"""
Connector schemas.

This module defines the Pydantic schemas used to represent and validate
connector-related data in API responses and updates.

Schemas:
    - ConnectorResponse: Returned by the API when retrieving connector details.
    - ConnectorUpdate: Used when updating an existing connector.

These schemas ensure consistency and proper validation for data
exchanged between the frontend and the backend.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.models.connector import PortConfig, Endpoints

class ConnectorResponse(BaseModel):
    """
    Represents a connector object returned by the API.

    This schema defines the structure of connector data retrieved from
    the database or exposed through the REST API.

    Example:
        >>> connector = ConnectorResponse(
        ...     id="edc-provider-01",
        ...     name="EDC Provider",
        ...     type="provider",
        ...     state="running",
        ...     mode="managed",
        ...     ports=PortConfig(http=8181, management=9999, protocol=8282, control=9191, public=8182, version=1)
        ... )
        >>> print(connector.name)
        EDC Provider
    """

    id: str
    """Unique identifier of the connector."""

    name: str
    """Human-readable name of the connector."""

    description: Optional[str] = None
    """Optional description providing additional connector details."""

    type: Literal["provider", "consumer"]
    """Role of the connector in data exchange (`provider` or `consumer`)."""

    ports: Optional[PortConfig] = None
    """Port configuration details for the connector."""
    
    state: Literal["running", "stopped"]
    """Operational state of the connector (`running` or `stopped`)."""

    mode: Literal["managed", "remote"]
    """Indicates whether the connector runs locally (`managed`) or remotely (`remote`)."""

    endpoints_url: Optional[Endpoints] = None
    """Management and protocol endpoint URLs associated with the connector."""

    api_key: Optional[str] = None
    """Authentication key for the connector, if applicable."""
    
    domain: Optional[str] = None
    """Public domain name of the connector.

    Specifies the external hostname where the connector is accessible 
    (e.g., ``edc-provider.mycompany.com``). This field is required when 
    the connector is deployed on a remote server and must be reachable 
    by other EDC connectors. 

    For local environments or isolated testing, this field can be left 
    empty or set to ``localhost``.
    """ 

class ConnectorUpdate(BaseModel):
    """
    Represents the schema used to update existing connector configurations.

    All fields are optional to allow partial updates.

    Example:
        >>> update = ConnectorUpdate(
        ...     name="Updated Provider",
        ...     state="stopped",
        ...     mode="remote"
        ... )
        >>> print(update.state)
        stopped
    """

    name: Optional[str]
    """Updated connector name."""

    description: Optional[str]
    """Updated description for the connector."""

    type: Optional[Literal["provider", "consumer"]]
    """Updated connector type (`provider` or `consumer`)."""

    ports: Optional[PortConfig]
    """Updated port configuration."""

    state: Optional[Literal["running", "stopped"]]
    """Updated operational state (`running` or `stopped`)."""

    mode: Optional[Literal["managed", "remote"]]
    """Updated deployment mode (`managed` or `remote`)."""

    endpoints_url: Optional[Endpoints] = None
    """Updated management and protocol endpoint URLs."""

    domain: Optional[str] = None
    """Public domain name of the connector.

    Specifies the external hostname where the connector is accessible 
    (e.g., ``edc-provider.mycompany.com``). This field is required when 
    the connector is deployed on a remote server and must be reachable 
    by other EDC connectors. 

    For local environments or isolated testing, this field can be left 
    empty or set to ``localhost``.
    """ 
