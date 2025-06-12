from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.models.connector import PortConfig, Endpoints

class ConnectorResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    type: Literal["provider", "consumer"]
    ports: Optional[PortConfig] = None
    state: Literal["running", "stopped"]
    mode: Literal["managed", "remote"]
    endpoints_url: Optional[Endpoints] = None
    api_key: Optional[str] = None

class ConnectorUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    type: Optional[Literal["provider", "consumer"]]
    ports: Optional[PortConfig]
    api_key: Optional[str] = None
    state: Optional[Literal["running", "stopped"]]
    mode: Optional[Literal["managed", "unmanaged"]]
    endpoints_url: Optional[Endpoints] = None