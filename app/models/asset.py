"""
Asset model definition.

This module defines the `Asset` data model used to represent
assets managed by the EDC Studio Backend. An asset is any data resource
(HTTP or file-based) that can be published, transferred, or managed
through the Eclipse Data Connector (EDC).

The model is implemented using Pydantic for data validation and type
hinting, ensuring consistency across the API and MongoDB storage.
"""

from typing import Literal
from pydantic import BaseModel


class Asset(BaseModel):
    """
    Represents an asset managed by the EDC Studio Backend.

    This model defines the structure and metadata of a registered asset,
    including its identifier, type, and connection parameters.

    Example:
        >>> asset = Asset(
        ...     asset_id="asset-001",
        ...     name="Weather Dataset",
        ...     content_type="application/json",
        ...     data_address_name="weather-data",
        ...     data_address_type="HttpData",
        ...     data_address_proxy=False,
        ...     base_url="https://data.server.com/weather",
        ...     edc="edc-provider-01"
        ... )
        >>> print(asset.name)
        Weather Dataset
    """
    
    asset_id: str
    """Unique identifier of the asset within EDC."""

    name: str
    """Human-readable name of the asset."""

    content_type: str
    """MIME type of the asset (e.g., `application/json`)."""

    data_address_name: str
    """Name of the data address configured in EDC."""

    data_address_type: Literal["HttpData", "File"]
    """Type of data address (`HttpData` or `File`)."""

    data_address_proxy: bool
    """Whether the data address uses proxying."""

    base_url: str
    """Base URL or path where the asset is located."""

    edc: str
    """Identifier of the EDC connector associated with the asset."""