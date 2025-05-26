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

class Connector(BaseModel):
    name: str
    description: Optional[str] = None
    type: Literal["provider", "consumer"]
    ports: Optional[PortConfig] = None
    keystore_password: Optional[str] = Field(min_length=6)
    state: Literal["running", "stopped"]
    mode: Literal["managed", "remote"]
    endpoint_url: Optional[str]