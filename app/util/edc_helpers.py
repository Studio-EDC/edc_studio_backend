"""
EDC helpers.

Utility functions to build EDC Management API URLs and to retrieve
authentication data for a given connector document.

Responsibilities:
    - Compose base management URLs for managed and remote connectors.
    - Validate and return the API key configured for a connector.
"""

import os
from dotenv import load_dotenv
from fastapi import HTTPException


def get_base_url(connector: dict, path: str) -> str:
    """
    Builds the base Management API URL for a connector and appends a path.

    For connectors in `managed` mode, the URL depends on the deployment type:
    - If TYPE=localhost (default), it uses localhost and the configured port.
    - Otherwise, it targets the Docker service name pattern:
      `edc-{type}-{_id}:{management_port}`.

    For connectors in `remote` mode, it uses the `endpoints_url.management`
    value provided in the connector document.

    Args:
        connector (dict): Connector document (from MongoDB) containing
            `mode`, `ports.management`, `type`, `_id`,
            and/or `endpoints_url.management`.
        path (str): Path to append to the base management URL
            (e.g., "/management/v3/assets").

    Raises:
        HTTPException: If the connector mode is invalid.

    Returns:
        str: Fully qualified URL to call the EDC Management API.
    """

    load_dotenv()
    
    if connector["mode"] == "managed":
        management_port = connector["ports"]["management"]
        if os.getenv("TYPE", "localhost") == 'localhost': return f"http://localhost:{management_port}/management{path}"
        else: return f"http://edc-{connector['type']}-{str(connector['_id'])}:{management_port}/management{path}"
    elif connector["mode"] == "remote":
        return f"{connector['endpoints_url']['management'].rstrip('/')}{path}"
    else:
        raise HTTPException(status_code=400, detail="Invalid connector mode")


def get_api_key(connector: dict) -> str:
    """
    Returns the API key configured for the connector.

    Args:
        connector (dict): Connector document containing an `api_key` field.

    Raises:
        HTTPException: If the API key is missing or empty.

    Returns:
        str: API key string to be used in `x-api-key` header.
    """
    
    api_key = connector.get("api_key")
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")
    return api_key