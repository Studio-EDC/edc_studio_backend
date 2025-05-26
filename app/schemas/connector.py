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
    keystore_password: Optional[str] = Field(default=None, min_length=6)

class ConnectorUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    type: Optional[Literal["provider", "consumer"]]
    ports: Optional[PortConfig]
    keystore_password: Optional[str] = Field(default=None, min_length=6)
    state: Optional[Literal["running", "stopped"]]
    mode: Optional[Literal["managed", "unmanaged"]]
    endpoints_url: Optional[Endpoints] = None