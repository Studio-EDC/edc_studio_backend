from typing import Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID, uuid4

class PortConfig(BaseModel):
    http: int
    management: int
    protocol: int
    control: int
    public: int
    version: int

class Endpoints(BaseModel):
    management: str
    protocol: Optional[str] = None

class Connector(BaseModel):
    name: str
    description: Optional[str] = None
    type: Literal["provider", "consumer"]
    ports: Optional[PortConfig] = None
    api_key: Optional[str] = None
    state: Literal["running", "stopped"]
    mode: Literal["managed", "remote"]
    endpoints_url: Optional[Endpoints] = None