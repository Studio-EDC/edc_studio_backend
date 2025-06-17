from fastapi import HTTPException


def get_base_url(connector: dict, path: str) -> str:
    if connector["mode"] == "managed":
        management_port = connector["ports"]["management"]
        return f"http://localhost:{management_port}{path}"
    elif connector["mode"] == "remote":
        return f"{connector['endpoints_url']['management'].rstrip('/')}{path}"
    else:
        raise HTTPException(status_code=400, detail="Invalid connector mode")


def get_api_key(connector: dict) -> str:
    api_key = connector.get("api_key")
    if not api_key:
        raise HTTPException(status_code=500, detail="Connector API key not configured")
    return api_key